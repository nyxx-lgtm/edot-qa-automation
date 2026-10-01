"""3B - AI failure triage over Allure results. Run after the suite:

    python -m ai.triage                  # reproduce each failure twice, write reports/triage_report.md
    python -m ai.triage --reproduce 0    # no re-runs (reproducibility left unknown)

For every failed/broken test it walks the evidence in the order the brief prescribes and
stops at the first match:
  1. Exception (timeout, element not found...) rather than an assertion  -> script/environment
  2. Locator did not resolve, was not unique, or hit the wrong element     -> script/environment
  3. An earlier step or a fixture/precondition failed                       -> script/environment
  4. The expected value itself is wrong for the test case                   -> script/environment
  5. Re-runs: passes sometimes -> flaky; fails every time -> product bug

Steps 1, 2 (unresolved/not unique), 3 and 5 are deterministic rules. Claude only answers the two
judgement calls rules cannot make (2: "is this the *intended* element?", 4: "is the expected value
right?"). Its answers are schema-validated; the verdict itself is always computed by this code.

Guardrails: this script only reads results and writes a report. It never edits tests, never files
or closes anything, and a failed test stays failed - every verdict is a proposal for a human.
"""
import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from pydantic import BaseModel, ConfigDict, ValidationError

from ai.prompts import TRIAGE_SYSTEM_PROMPT, TRIAGE_USER_PROMPT
from config import settings

SCRIPT = "script/environment defect"
PRODUCT = "product bug"
FLAKY = "flaky"

MESSAGE_LIMIT = 3000  # characters of failure message/call log sent to the model (token budget)


# ---------- reading Allure results ----------

@dataclass
class Failure:
    title: str
    status: str               # "failed" (assertion) or "broken" (exception)
    nodeid: str
    message: str
    trace: str
    steps: list[tuple[str, str]]
    failed_fixtures: list[str]
    test_data: str
    source: str


def load_failures(results_dir: Path) -> list[Failure]:
    results = [json.loads(p.read_text(encoding="utf-8")) for p in results_dir.glob("*-result.json")]
    containers = [json.loads(p.read_text(encoding="utf-8")) for p in results_dir.glob("*-container.json")]
    test_data = _find_test_data(results_dir)

    failures = []
    for r in results:
        if r["status"] not in ("failed", "broken"):
            continue
        details = r.get("statusDetails") or {}
        failures.append(Failure(
            title=r["name"],
            status=r["status"],
            nodeid=_nodeid(r),
            message=details.get("message", ""),
            trace=details.get("trace", ""),
            steps=_flatten_steps(r.get("steps", [])),
            failed_fixtures=[fx["name"] for c in containers if r["uuid"] in c.get("children", [])
                             for fx in c.get("befores", []) if fx.get("status") in ("failed", "broken")],
            test_data=test_data,
            source=_test_source(r),
        ))
    return failures


def _label(result: dict, name: str) -> str | None:
    return next((lb["value"] for lb in result.get("labels", []) if lb["name"] == name), None)


def _nodeid(result: dict) -> str:
    path = _label(result, "package").replace(".", "/") + ".py"
    method = result["fullName"].split("#")[-1]
    cls = _label(result, "subSuite")
    return f"{path}::{cls}::{method}" if cls else f"{path}::{method}"


def _flatten_steps(steps: list, depth: int = 0) -> list[tuple[str, str]]:
    flat = []
    for s in steps:
        flat.append(("  " * depth + s["name"], s["status"]))
        flat.extend(_flatten_steps(s.get("steps", []), depth + 1))
    return flat


def _find_test_data(results_dir: Path) -> str:
    """The generated-data attachment written by the `generated_data` fixture."""
    for p in results_dir.glob("*-attachment.json"):
        text = p.read_text(encoding="utf-8")
        if '"source"' in text and '"data"' in text:
            return text
    return "{}"


def _test_source(result: dict) -> str:
    path = settings.ROOT_DIR / (_label(result, "package").replace(".", "/") + ".py")
    method = result["fullName"].split("#")[-1]
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except OSError:
        return ""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method:
            return ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
    return ""


# ---------- the evidence walk ----------

class Judgement(BaseModel):
    """What Claude may contribute: two narrow answers, validated before use."""
    model_config = ConfigDict(extra="forbid")
    locator_is_intended: bool | None
    locator_reason: str
    expected_value_is_correct: bool | None
    expected_reason: str


JUDGEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "locator_is_intended": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "locator_reason": {"type": "string"},
        "expected_value_is_correct": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "expected_reason": {"type": "string"},
    },
    "required": ["locator_is_intended", "locator_reason", "expected_value_is_correct", "expected_reason"],
    "additionalProperties": False,
}


@dataclass
class Verdict:
    failure: Failure
    verdict: str
    stopped_at: str
    evidence: list[str] = field(default_factory=list)
    ai_note: str = ""
    reruns: list[str] = field(default_factory=list)


def triage(failure: Failure, reproduce: int, client: anthropic.Anthropic | None) -> Verdict:
    msg = failure.message + "\n" + failure.trace
    first_line = failure.message.strip().splitlines()[0] if failure.message.strip() else "(no message)"

    # 1. Exception or assertion?
    if failure.status == "broken" or not first_line.startswith("AssertionError"):
        return Verdict(failure, SCRIPT, "1 - exception, not an assertion",
                       [f"Raised: `{first_line[:200]}`",
                        "An exception (timeout, element not found, error in a fixture) means the test could "
                        "not reach its check; it is almost always the script or the environment."])

    # 2a. Did the locator resolve, and to exactly one element? (rules)
    if "strict mode violation" in msg:
        return Verdict(failure, SCRIPT, "2 - locator not unique", ["Call log: `strict mode violation` - "
                       "the locator matched several elements."])
    if "waiting for" in msg and "resolved to" not in msg:
        return Verdict(failure, SCRIPT, "2 - locator did not resolve",
                       [f"Call log waits for {_quote_line(msg, 'waiting for')} but never shows "
                        "`locator resolved to` - no element matched."])

    # 3. Did every earlier step and precondition succeed?
    if failure.failed_fixtures:
        return Verdict(failure, SCRIPT, "3 - precondition failed",
                       [f"Fixture(s) failed: {', '.join(failure.failed_fixtures)}"])
    # Only top-level steps: a failing nested step also marks its parents failed. The last
    # top-level step is the one that holds the failing assertion.
    top_level = [(name, status) for name, status in failure.steps if not name.startswith(" ")]
    earlier = [name for name, status in top_level[:-1] if status != "passed"]
    if earlier:
        return Verdict(failure, SCRIPT, "3 - an earlier step failed", [f"Earlier step(s) not passed: {earlier}"])

    evidence = ["It is an assertion failure (`AssertionError`), not an exception.",
                "The locator resolved to a single element." if "resolved to" in msg else "Plain assert - no locator involved.",
                "Every earlier step and every fixture passed."]

    # 2b + 4. Judgement calls - Claude, if available.
    judgement, ai_note = _ask_claude(failure, client)
    if judgement and judgement.locator_is_intended is False:
        return Verdict(failure, SCRIPT, "2 - locator hit the wrong element", evidence + [
            f"AI (proposal): {judgement.locator_reason}"], ai_note)
    if judgement and judgement.expected_value_is_correct is False:
        return Verdict(failure, SCRIPT, "4 - expected value is wrong", evidence + [
            f"AI (proposal): {judgement.expected_reason}"], ai_note)
    if judgement:
        evidence += [f"AI: locator - {judgement.locator_reason}", f"AI: expected value - {judgement.expected_reason}"]
    else:
        evidence.append("Steps 2 (intended element) and 4 (expected value) were NOT reviewed - see AI note.")

    # 5. Does it reproduce?
    reruns = _reproduce(failure.nodeid, reproduce)
    if not reruns:
        return Verdict(failure, PRODUCT + " (reproducibility not checked)", "5 - no re-runs requested",
                       evidence, ai_note)
    if "passed" in reruns:
        return Verdict(failure, FLAKY, "5 - intermittent",
                       evidence + [f"Re-runs: {reruns} - it passes sometimes, so it is flaky, not a bug."], ai_note, reruns)
    return Verdict(failure, PRODUCT, "5 - reproduces every time",
                   evidence + [f"Re-runs: {reruns} - fails consistently."], ai_note, reruns)


def _quote_line(text: str, needle: str) -> str:
    line = next((ln.strip() for ln in text.splitlines() if needle in ln), needle)
    return f"`{line[:160]}`"


def _ask_claude(failure: Failure, client: anthropic.Anthropic | None) -> tuple[Judgement | None, str]:
    if client is None:
        return None, "AI unavailable (no ANTHROPIC_API_KEY) - rules-only triage."
    prompt = TRIAGE_USER_PROMPT.format(
        title=failure.title,
        source=failure.source or "(source not found)",
        message=(failure.message + "\n" + failure.trace)[:MESSAGE_LIMIT],
        steps="\n".join(f"- [{status}] {name}" for name, status in failure.steps) or "(none)",
        test_data=failure.test_data,
    )
    try:
        response = client.beta.messages.create(
            model=settings.AI_TRIAGE_MODEL,
            max_tokens=4000,
            system=TRIAGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": JUDGEMENT_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as e:
        return None, f"AI call failed ({type(e).__name__}) - rules-only triage."
    if response.stop_reason != "end_turn":
        return None, f"AI returned no usable answer (stop_reason={response.stop_reason}) - rules-only triage."
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return Judgement.model_validate_json(text), f"AI: {response.model}, {response.usage.input_tokens} in / {response.usage.output_tokens} out tokens"
    except ValidationError as e:
        return None, f"AI answer rejected by schema ({e.error_count()} error(s)) - rules-only triage."


def _reproduce(nodeid: str, times: int) -> list[str]:
    outcomes = []
    for _ in range(times):
        with tempfile.TemporaryDirectory() as tmp:
            # A separate results dir: re-runs never overwrite the evidence being triaged.
            run = subprocess.run([sys.executable, "-m", "pytest", nodeid, "-q", f"--alluredir={tmp}"],
                                 cwd=settings.ROOT_DIR, env=os.environ.copy(), capture_output=True, text=True)
        outcomes.append("passed" if run.returncode == 0 else "failed")
    return outcomes


# ---------- report ----------

def render(verdicts: list[Verdict]) -> str:
    lines = ["# Failure triage report", "",
             "> Every verdict below is a **proposal for a human reviewer**. Nothing was filed, closed, "
             "re-written or skipped; failed tests remain failed.", ""]
    if not verdicts:
        return "\n".join(lines + ["No failed or broken tests in these results."])
    lines += ["| Test | Verdict | Stopped at |", "|---|---|---|"]
    lines += [f"| {v.failure.title} | **{v.verdict}** | {v.stopped_at} |" for v in verdicts]
    for v in verdicts:
        lines += ["", f"## {v.failure.title}", "", f"- **Verdict (proposal):** {v.verdict}",
                  f"- **Stopped at evidence step:** {v.stopped_at}", f"- **Test:** `{v.failure.nodeid}`",
                  f"- **Allure status:** {v.failure.status}", "", "**Evidence**", ""]
        lines += [f"- {e}" for e in v.evidence]
        if v.ai_note:
            lines += ["", f"_{v.ai_note}_"]
        lines += ["", "<details><summary>Failure message</summary>", "", "```",
                  v.failure.message.strip()[:1500], "```", "</details>"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default=str(settings.ROOT_DIR / "allure-results"))
    parser.add_argument("--out", default=str(settings.ROOT_DIR / "reports" / "triage_report.md"))
    parser.add_argument("--reproduce", type=int, default=2, help="re-runs per failure for the flakiness check")
    args = parser.parse_args()

    client = anthropic.Anthropic() if settings.ANTHROPIC_API_KEY else None
    verdicts = [triage(f, args.reproduce, client) for f in load_failures(Path(args.results))]

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(render(verdicts), encoding="utf-8")
    print(f"{len(verdicts)} failure(s) triaged -> {out}")


if __name__ == "__main__":
    main()
