"""Offline tests for 3A. A fake client stands in for Claude so no key or network is needed."""
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from ai import data_generator
from ai.data_generator import generate_test_data
from ai.schemas import TestData
from config import settings

pytestmark = pytest.mark.unit

VALID = {
    "company": {
        "legal_name": "PT Sinar Jaya Niaga",
        "email": "sales@sinarjaya.example.com",
        "phone": "81234567890",
        "street_address": "Jl. Wolter Monginsidi No. 12",
        "industry": "Retail",
    },
    "customer": {
        "name": "Toko Berkah Abadi",
        "contact_person": "Budi Santoso",
        "phone": "85712345678",
        "email": "owner@berkah.example.com",
        "street_address": "Jl. Kemang Raya No. 5",
    },
}


class FakeClient:
    """Returns the queued replies in order; a queued exception is raised instead."""

    def __init__(self, *replies):
        self._replies = list(replies)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


def test_valid_ai_output_is_used_and_tagged():
    result = generate_test_data(FakeClient(VALID))

    assert result.source == settings.AI_DATA_MODEL
    assert result.data.company.legal_name == f"PT Sinar Jaya Niaga QA{settings.RUN_ID}"
    assert result.data.company.email == f"sales.qa{settings.RUN_ID.lower()}@sinarjaya.example.com"
    assert result.data.company.phone == "81234567890"


def test_malformed_output_is_retried_with_the_error_then_accepted():
    bad = json.loads(json.dumps(VALID))
    bad["company"]["phone"] = "+62 812-3456"
    client = FakeClient(bad, VALID)

    result = generate_test_data(client)

    assert result.source == settings.AI_DATA_MODEL
    assert len(client.calls) == 2
    assert "rejected by schema validation" in client.calls[1]["messages"][0]["content"]
    assert "rejected by schema" in result.attempts[0]


def test_invalid_twice_falls_back_to_faker():
    result = generate_test_data(FakeClient("not json at all", {"company": {}}))

    assert result.source == "faker-fallback"
    assert len(result.attempts) == 2


def test_api_error_falls_back_without_extra_retries():
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    client = FakeClient(error)

    result = generate_test_data(client)

    assert result.source == "faker-fallback"
    assert len(client.calls) == 1


def test_no_api_key_uses_faker(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")

    result = generate_test_data()

    assert result.source == "faker-fallback"
    assert "not set" in result.attempts[0]


@pytest.mark.parametrize("run_id", ["A1B2C3", "FFFFFF", "000000", "QWERTY", "123456"])
def test_tagged_company_name_fits_the_30_char_ui_limit(monkeypatch, run_id):
    monkeypatch.setattr(settings, "RUN_ID", run_id)

    result = generate_test_data(FakeClient("not json", "still not json"))  # forces the Faker path

    assert len(result.data.company.legal_name) <= 30


def test_synthetic_ktp_is_16_digits_and_stable():
    assert data_generator.synthetic_ktp() == data_generator.synthetic_ktp()
    assert len(data_generator.synthetic_ktp()) == 16 and data_generator.synthetic_ktp().isdigit()


def test_faker_fallback_is_schema_valid_and_deterministic():
    first = TestData.model_validate(data_generator._faker_data())
    second = TestData.model_validate(data_generator._faker_data())

    assert first == second


@pytest.mark.parametrize("field, value", [
    ("legal_name", "Sinar Jaya"),            # missing PT/CV prefix
    ("legal_name", "PT Sinar Jaya Niaga Abadi"),  # 25 chars: no room for the run tag
    ("email", "sales@sinarjaya.co.id"),      # real-looking domain not allowed
    ("phone", "0812345678"),                 # leading 0 not allowed after +62
    ("industry", "Space Mining"),            # not an eSuite option
])
def test_schema_rejects_bad_company_fields(field, value):
    bad = json.loads(json.dumps(VALID))
    bad["company"][field] = value

    with pytest.raises(ValueError):
        TestData.model_validate(bad)
