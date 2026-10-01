"""3A - AI-generated test data with schema validation and a deterministic fallback.

Flow:
  1. No API key            -> Faker fallback (suite still runs offline / in CI).
  2. Ask Claude for JSON   -> validate with the Pydantic schema.
  3. Invalid output        -> retry once, telling the model what was wrong.
  4. Still invalid / API error / refusal -> Faker fallback.
  5. Whatever the source, the data is validated by the same schema and tagged with RUN_ID.

The result records its source and every attempt, so the Allure attachment shows
exactly where the data came from and why.
"""
import json
import random
from dataclasses import dataclass, field

import anthropic
from faker import Faker
from pydantic import ValidationError

from ai.prompts import DATA_RETRY_SUFFIX, DATA_SYSTEM_PROMPT, DATA_USER_PROMPT
from ai.schemas import API_JSON_SCHEMA, COMPANY_NAME_MAX, RUN_TAG_LEN, CompanyData, CustomerData, TestData
from config import settings
from config.test_constants import INDUSTRY_OPTIONS

MAX_AI_ATTEMPTS = 2


@dataclass
class GenerationResult:
    data: TestData
    source: str                      # e.g. "claude-haiku-4-5" or "faker-fallback"
    attempts: list[str] = field(default_factory=list)

    def to_report(self) -> str:
        return json.dumps(
            {"source": self.source, "attempts": self.attempts, "data": self.data.model_dump()},
            indent=2,
            ensure_ascii=False,
        )


def generate_test_data(client: anthropic.Anthropic | None = None) -> GenerationResult:
    attempts: list[str] = []

    if client is None and not settings.ANTHROPIC_API_KEY:
        attempts.append("ANTHROPIC_API_KEY not set - AI skipped")
    else:
        client = client or anthropic.Anthropic()
        data = _generate_with_ai(client, attempts)
        if data is not None:
            return GenerationResult(_apply_run_tag(data), settings.AI_DATA_MODEL, attempts)

    data = TestData.model_validate(_faker_data())
    return GenerationResult(_apply_run_tag(data), "faker-fallback", attempts)


def _generate_with_ai(client: anthropic.Anthropic, attempts: list[str]) -> TestData | None:
    prompt = DATA_USER_PROMPT
    for attempt in range(1, MAX_AI_ATTEMPTS + 1):
        try:
            response = client.messages.create(
                model=settings.AI_DATA_MODEL,
                max_tokens=1024,  # the reply is ~250 tokens of JSON; this cap keeps cost bounded
                system=DATA_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": API_JSON_SCHEMA}},
            )
        except anthropic.APIError as e:
            # Network / auth / rate limit: the SDK already retried transient errors.
            # Retrying again here would only burn time, so go straight to the fallback.
            attempts.append(f"attempt {attempt}: API error {type(e).__name__}: {e}")
            return None

        if response.stop_reason != "end_turn":
            attempts.append(f"attempt {attempt}: unusable stop_reason={response.stop_reason}")
            continue

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = TestData.model_validate_json(text)
        except ValidationError as e:
            attempts.append(f"attempt {attempt}: rejected by schema: {e.errors(include_url=False)}")
            prompt = DATA_USER_PROMPT + DATA_RETRY_SUFFIX.format(error=e)
            continue

        attempts.append(f"attempt {attempt}: accepted")
        return data

    return None


def _faker_data() -> dict:
    # Seeded with RUN_ID: the same run id always reproduces the same data.
    fake = Faker("id_ID")
    fake.seed_instance(settings.RUN_ID)
    rng = random.Random(settings.RUN_ID)

    surname = fake.last_name()
    suffixed = f"{surname} {rng.choice(['Jaya', 'Makmur', 'Abadi', 'Niaga', 'Utama'])}"
    # Keep "PT <brand>" within the 21 characters left after the run tag (30-char UI limit).
    brand = suffixed if len(f"PT {suffixed}") <= COMPANY_NAME_MAX - RUN_TAG_LEN else surname
    slug = brand.lower().replace(" ", "")
    return {
        "company": {
            "legal_name": f"PT {brand}",
            "email": f"sales@{slug}.example.com",
            "phone": fake.numerify("8##########"),
            "street_address": f"{fake.street_name()} No. {rng.randint(1, 199)}",
            "industry": rng.choice(INDUSTRY_OPTIONS),
        },
        "customer": {
            "name": f"Toko {fake.first_name()} {fake.last_name()}"[:30],
            "contact_person": f"{fake.first_name()} {fake.last_name()}"[:30],
            "phone": fake.numerify("8##########"),
            "email": f"owner@toko{slug}.example.com",
            "street_address": f"{fake.street_name()} No. {rng.randint(1, 199)}",
        },
    }


def synthetic_ktp() -> str:
    """16-digit KTP (Indonesian ID) number for the mobile form - fake, deterministic, never from the AI.

    3174 = Jakarta Selatan region code, 010190 = a fixed birth date, then 6 digits derived from RUN_ID.
    """
    return "3174010190" + f"{int(settings.RUN_ID, 36) % 1_000_000:06d}"


def _apply_run_tag(data: TestData) -> TestData:
    """Make records unique per run and easy to find for cleanup, e.g. 'PT Sinar Jaya QA7F3A2B'."""
    tag = f"QA{settings.RUN_ID}"
    company = data.company.model_copy(update={
        "legal_name": f"{data.company.legal_name} {tag}",
        "email": _tag_email(data.company.email, tag),
    })
    customer = data.customer.model_copy(update={
        "name": f"{data.customer.name} {tag}",
        "email": _tag_email(data.customer.email, tag),
    })
    # Re-validate: tagging must never produce data the schema (or eSuite) would reject.
    return TestData(company=CompanyData.model_validate(company.model_dump(), context={"tagged": True}),
                    customer=CustomerData.model_validate(customer.model_dump()))


def _tag_email(email: str, tag: str) -> str:
    local, domain = email.split("@", 1)
    return f"{local}.{tag.lower()}@{domain}"
