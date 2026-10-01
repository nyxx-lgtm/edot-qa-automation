"""Offline tests for 3B: every branch of the evidence walk, with a fake Claude and stubbed re-runs."""
import json
from types import SimpleNamespace

import pytest

from ai import triage as t

pytestmark = pytest.mark.unit

UNRESOLVED = """AssertionError: Locator expected to be visible
Call log:
  - waiting for get_by_text("Please enter a valid email")"""

RESOLVED = """AssertionError: Locator expected to have Value 'sales.qa1@x.example.com'
Actual value: PT Sinar Jaya QA1
Call log:
  - waiting for get_by_placeholder("Input Company Name")
    - locator resolved to <input placeholder="Input Company Name" value="PT Sinar Jaya QA1"/>"""


def failure(message=RESOLVED, status="failed", steps=None, fixtures=None):
    return t.Failure(title="WEB-COMP-02 detail", status=status, nodeid="web/tests/test_company.py::T::test_x",
                     message=message, trace="", steps=steps or [("Identity", "passed"), ("Contact", "failed")],
                     failed_fixtures=fixtures or [], test_data="{}", source="def test_x(): ...")


def fake_client(judgement: dict | str):
    text = judgement if isinstance(judgement, str) else json.dumps(judgement)
    reply = SimpleNamespace(stop_reason="end_turn", model="claude-sonnet-5-5",
                            content=[SimpleNamespace(type="text", text=text)],
                            usage=SimpleNamespace(input_tokens=900, output_tokens=120))
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: reply)))


def judgement(locator=True, expected=True):
    return {"locator_is_intended": locator, "locator_reason": "r1",
            "expected_value_is_correct": expected, "expected_reason": "r2"}


@pytest.fixture
def reruns(monkeypatch):
    def set_outcomes(*outcomes):
        monkeypatch.setattr(t, "_reproduce", lambda nodeid, times: list(outcomes)[:times])
    return set_outcomes


def test_exception_is_script_defect():
    v = t.triage(failure("playwright._impl._errors.TimeoutError: Locator.click: Timeout", status="broken"), 0, None)
    assert (v.verdict, v.stopped_at[0]) == (t.SCRIPT, "1")


def test_unresolved_locator_is_script_defect():
    v = t.triage(failure(UNRESOLVED), 0, None)
    assert (v.verdict, v.stopped_at) == (t.SCRIPT, "2 - locator did not resolve")


def test_strict_mode_violation_is_script_defect():
    v = t.triage(failure("AssertionError: strict mode violation: resolved to 2 elements"), 0, None)
    assert v.stopped_at == "2 - locator not unique"


def test_failed_fixture_is_script_defect():
    v = t.triage(failure(fixtures=["registered_company"]), 0, None)
    assert (v.verdict, v.stopped_at[0]) == (t.SCRIPT, "3")


def test_ai_says_wrong_element(reruns):
    reruns("failed", "failed")
    v = t.triage(failure(), 2, fake_client(judgement(locator=False)))
    assert (v.verdict, v.stopped_at) == (t.SCRIPT, "2 - locator hit the wrong element")


def test_ai_says_expected_value_wrong(reruns):
    reruns("failed", "failed")
    v = t.triage(failure(), 2, fake_client(judgement(expected=False)))
    assert v.stopped_at == "4 - expected value is wrong"


def test_consistent_failure_with_clean_evidence_is_product_bug(reruns):
    reruns("failed", "failed")
    v = t.triage(failure(), 2, fake_client(judgement()))
    assert (v.verdict, v.stopped_at) == (t.PRODUCT, "5 - reproduces every time")


def test_intermittent_failure_is_flaky(reruns):
    reruns("passed", "failed")
    v = t.triage(failure(), 2, fake_client(judgement()))
    assert v.verdict == t.FLAKY


def test_invalid_ai_answer_falls_back_to_rules_and_says_so(reruns):
    reruns("failed", "failed")
    v = t.triage(failure(), 2, fake_client('{"verdict": "product bug"}'))
    assert v.verdict == t.PRODUCT
    assert "rejected by schema" in v.ai_note
    assert any("NOT reviewed" in e for e in v.evidence)


def test_no_api_key_is_rules_only(reruns):
    reruns("failed", "failed")
    v = t.triage(failure(), 2, None)
    assert "no ANTHROPIC_API_KEY" in v.ai_note


def test_report_is_labelled_as_proposal():
    report = t.render([t.triage(failure(UNRESOLVED), 0, None)])
    assert "proposal for a human reviewer" in report
    assert "Nothing was filed, closed" in report


def test_load_failures_reads_allure_results(tmp_path):
    result = {"name": "WEB-COMP-03", "status": "failed", "uuid": "u1", "fullName": "web.tests.test_company.TestCompany#test_invalid_email_is_rejected",
              "statusDetails": {"message": UNRESOLVED, "trace": ""},
              "steps": [{"name": "Open Companies", "status": "passed", "steps": []}],
              "labels": [{"name": "package", "value": "web.tests.test_company"}, {"name": "subSuite", "value": "TestCompany"}]}
    (tmp_path / "u1-result.json").write_text(json.dumps(result))
    (tmp_path / "ok-result.json").write_text(json.dumps({**result, "uuid": "u2", "status": "passed"}))

    [f] = t.load_failures(tmp_path)

    assert f.nodeid == "web/tests/test_company.py::TestCompany::test_invalid_email_is_rejected"
    assert "def test_invalid_email_is_rejected" in f.source
