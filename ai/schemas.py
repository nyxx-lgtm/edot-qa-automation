"""Schema every piece of generated test data must pass before a test may use it.

Two layers, on purpose:
  * API_JSON_SCHEMA  - sent to the model so the *shape* of the reply is constrained.
  * Pydantic models  - enforce the *business rules* (formats, lengths, allowed values).
    These run on AI output and on Faker output alike, so both paths are held to the same bar.
"""
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator

from config.test_constants import INDUSTRY_OPTIONS

# Indonesian mobile number as typed after eSuite's fixed "+62" prefix: 8 + 8..11 digits.
PHONE_PATTERN = r"^8\d{8,11}$"
# Company emails must live under example.com (RFC 2606, reserved for testing) so a
# shared environment never sends mail to a real business.
TEST_EMAIL_DOMAIN = "example.com"
# eSuite's Company Name input silently refuses anything longer than 30 characters.
COMPANY_NAME_MAX = 30
# Every record gets " QA" + 6-char RUN_ID appended, so the generated part must leave room.
RUN_TAG_LEN = 9
CUSTOMER_NAME_MAX = 40


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CompanyData(_Strict):
    legal_name: str = Field(min_length=6, max_length=COMPANY_NAME_MAX)
    email: EmailStr
    phone: str = Field(pattern=PHONE_PATTERN)
    street_address: str = Field(min_length=10, max_length=120)
    industry: str

    @field_validator("legal_name")
    @classmethod
    def legal_entity_name(cls, v: str, info: ValidationInfo) -> str:
        if not re.match(r"^(PT|CV) [A-Z]", v):
            raise ValueError("legal_name must start with 'PT ' or 'CV ' followed by a capitalised name")
        # Generated names must leave room for the run tag; tagged names must fit the UI limit.
        limit = COMPANY_NAME_MAX if (info.context or {}).get("tagged") else COMPANY_NAME_MAX - RUN_TAG_LEN
        if len(v) > limit:
            raise ValueError(f"legal_name must be at most {limit} characters")
        return v

    @field_validator("email")
    @classmethod
    def reserved_domain(cls, v: str) -> str:
        if not v.lower().endswith(TEST_EMAIL_DOMAIN):
            raise ValueError(f"email must use a subdomain of {TEST_EMAIL_DOMAIN}")
        return v

    @field_validator("industry")
    @classmethod
    def known_industry(cls, v: str) -> str:
        if v not in INDUSTRY_OPTIONS:
            raise ValueError(f"industry must be one of {INDUSTRY_OPTIONS}")
        return v


class CustomerData(_Strict):
    name: str = Field(min_length=3, max_length=CUSTOMER_NAME_MAX)
    contact_person: str = Field(min_length=2, max_length=40)
    phone: str = Field(pattern=PHONE_PATTERN)
    email: EmailStr
    street_address: str = Field(min_length=10, max_length=120)

    @field_validator("email")
    @classmethod
    def reserved_domain(cls, v: str) -> str:
        if not v.lower().endswith(TEST_EMAIL_DOMAIN):
            raise ValueError(f"email must use a subdomain of {TEST_EMAIL_DOMAIN}")
        return v


class TestData(_Strict):
    __test__ = False  # stop pytest trying to collect this class as a test
    company: CompanyData
    customer: CustomerData


def _obj(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


API_JSON_SCHEMA = _obj({
    "company": _obj({
        "legal_name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "street_address": {"type": "string"},
        "industry": {"type": "string", "enum": INDUSTRY_OPTIONS},
    }),
    "customer": _obj({
        "name": {"type": "string"},
        "contact_person": {"type": "string"},
        "phone": {"type": "string"},
        "email": {"type": "string"},
        "street_address": {"type": "string"},
    }),
})
