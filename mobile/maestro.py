"""Run a Maestro flow from pytest and attach its evidence to the same Allure run as the web suite."""
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import allure

from config import settings

FLOWS_DIR = settings.ROOT_DIR / "mobile" / "flows"
# The customer flow scrolls a shared list that grows with every candidate (~6 min at 285 entries).
FLOW_TIMEOUT_S = 1800
CUSTOMER_LEDGER = settings.ROOT_DIR / "handoff" / "created_customers.json"


@dataclass
class MaestroResult:
    returncode: int
    output: str          # already redacted
    output_dir: Path


def run_flow(flow: str, env: dict[str, str], secrets: list[str]) -> MaestroResult:
    """Run mobile/flows/<flow>. Every key in `env` reaches the flow as ${MAESTRO_<KEY>}.

    Values are passed as MAESTRO_* environment variables (Maestro exposes those to flows), so
    no credential appears on the command line or in any YAML file.
    """
    name = Path(flow).stem
    out_dir = settings.MOBILE_OUTPUT_DIR / f"{name}-{settings.RUN_ID}"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)

    cmd = [settings.MAESTRO_BIN, "test", str(FLOWS_DIR / flow),
           "--format", "junit", "--output", str(out_dir / "report.xml"),
           "--debug-output", str(out_dir / "debug"), "--flatten-debug-output"]
    process_env = {**os.environ, **{f"MAESTRO_{k}": str(v) for k, v in env.items()}}

    with allure.step(f"maestro test {flow}"):
        # cwd = out_dir so startRecording/takeScreenshot files land next to the report.
        proc = subprocess.Popen(cmd, cwd=out_dir, env=process_env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        try:
            stdout, _ = proc.communicate(timeout=FLOW_TIMEOUT_S)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            # maestro.bat starts a Java child; killing only the .bat would leave the flow running.
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            stdout, _ = proc.communicate()
            stdout += f"\n[wrapper] flow killed after {FLOW_TIMEOUT_S}s"
            returncode = -1
        output = redact(stdout, secrets)
        _attach_evidence(output, out_dir)
    return MaestroResult(returncode, output, out_dir)


def redact(text: str, secrets: list[str]) -> str:
    """Maestro echoes every inputText value - never let a password reach a report."""
    for secret in filter(None, secrets):
        text = text.replace(secret, "********")
    return text


def regex_escaped(values: dict[str, str]) -> dict[str, str]:
    """`<KEY>_RE` copies for use in Maestro text selectors, which are regular expressions."""
    return {f"{k}_RE": re.escape(v) for k, v in values.items()}


def _attach_evidence(output: str, out_dir: Path):
    clean = "\n".join(line for line in output.splitlines()
                      if "WARNING" not in line and not line.startswith("?"))
    allure.attach(clean, name="maestro output", attachment_type=allure.attachment_type.TEXT)
    for video in out_dir.rglob("*.mp4"):
        allure.attach.file(str(video), name=f"screen recording ({video.name})",
                           attachment_type=allure.attachment_type.MP4)
    for shot in sorted(out_dir.rglob("*.png")):
        allure.attach.file(str(shot), name=shot.stem, attachment_type=allure.attachment_type.PNG)


def log_created_customer(entry: dict):
    """eWork has no delete for customer registrations, so every one we submit is recorded here."""
    entries = json.loads(CUSTOMER_LEDGER.read_text()) if CUSTOMER_LEDGER.exists() else []
    CUSTOMER_LEDGER.write_text(json.dumps(entries + [entry], indent=2))
