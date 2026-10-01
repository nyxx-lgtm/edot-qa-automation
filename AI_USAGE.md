# AI usage

The suite uses Claude in two places, both inside the automation (not just in the editor):

| | 3A - test data | 3B - failure triage |
|---|---|---|
| Module | `ai/data_generator.py` | `ai/triage.py` |
| When it runs | **during** the run, once per session (`generated_data` fixture) | **after** the run (`python -m ai.triage`) |
| Model | `claude-haiku-4-5` | `claude-sonnet-5-5` |
| Output contract | JSON schema + Pydantic models (`ai/schemas.py`) | JSON schema + Pydantic `Judgement` model |
| Without a key / on bad output | deterministic Faker fallback | rules-only triage, stated in the report |

Both model names come from `.env` (`AI_DATA_MODEL`, `AI_TRIAGE_MODEL`). The key comes only from the
`ANTHROPIC_API_KEY` environment variable; `.env` is git-ignored and `.env.example` ships it empty.

## Which model, and why

- **Data: Claude Haiku 4.5.** The task is short and structured: ~250 tokens of JSON for one company and one
  customer. It needs plausible Indonesian names and addresses, not deep reasoning. Haiku is the fastest and
  cheapest model, and every answer is validated by our own schema anyway.
- **Triage: Claude Sonnet 5.5, effort `medium`.** It answers two judgement questions over a call log, a test
  function and the test data. That needs real reading comprehension, but not the most expensive tier. It is
  called only for failures the rules cannot settle (see below), so most runs make zero or one call.

## Where AI runs

1. **While writing the tests:** I (the candidate) used Claude Code as a pair programmer for exploration and code.
   Every line was reviewed, and the decisions are explained in the README and in comments.
2. **During the run:** 3A generates the test data.
3. **After the run:** 3B proposes a verdict for each failure.

## The exact prompts

All prompts live verbatim in `ai/prompts.py`; this section copies them.

### 3A - test data (`DATA_SYSTEM_PROMPT` + `DATA_USER_PROMPT`)

System:

```text
You generate realistic, fictional Indonesian business test data for an automated QA suite. Reply with JSON only, matching the provided schema exactly.
```

User:

```text
Generate one company and one customer for a B2B sales app in Indonesia.

Rules:
- company.legal_name: a plausible Indonesian legal entity, starting with "PT " or "CV ", 1-3 short words after the prefix, max 21 characters in total (e.g. "PT Sinar Jaya Niaga"). No real, well-known brands.
- company.industry: pick the option that best fits the company name.
- company.street_address and customer.street_address: a street line in Jakarta, e.g. "Jl. Wolter Monginsidi No. 12". No city, province or postal code - those are chosen separately.
- phone numbers: Indonesian mobile without the country code or leading 0 (the form shows +62 already), digits only, starting with 8, 9-12 digits in total, e.g. "81234567890".
- emails: must use a subdomain of example.com derived from the company, e.g. "sales@sinarjaya.example.com". Never use a real domain.
- customer.name: a retail shop (toko) that would buy from this company, max 30 characters.
- customer.contact_person: the shop owner's full Indonesian name, max 30 characters.
- The company, its industry and the customer should make sense together.
```

On a retry, this is appended (`DATA_RETRY_SUFFIX`), with `{error}` replaced by the Pydantic validation error:

```text
Your previous answer was rejected by schema validation:
{error}
Fix those fields and answer again.
```

The request also sends `output_config.format` = the JSON schema in `ai/schemas.py::API_JSON_SCHEMA`. The industry
is an `enum` of the 19 options that really exist in eSuite's dropdown, so the model can only *choose* a valid value.

### 3B - triage (`TRIAGE_SYSTEM_PROMPT` + `TRIAGE_USER_PROMPT`)

System:

```text
You review one failed UI test for a QA engineer. You answer two narrow questions with evidence quoted from the material you are given. You never suggest changing, weakening or skipping the test's assertions, and you never decide the final verdict - a human does. Reply with JSON only.
```

User (placeholders are filled from the Allure result):

~~~~text
A rule engine already established: the failure is an assertion (not an exception), the locator resolved, and every earlier step and fixture passed. Two questions remain.

Q1 - locator_is_intended: Did the assertion's locator resolve to the element the test meant to check? Compare what the test intends (its title, the page-object attribute name, the expected value) with the element the call log says was resolved (tag, placeholder, text). Answer null if there was no locator.

Q2 - expected_value_is_correct: Is the expected value in the assertion the right value according to the test case and the test data that was actually used? Answer null if you cannot tell from the material.

For each answer give a one or two sentence justification that quotes the specific evidence.

## Test
Title: {title}
Source:
```python
{source}
```

## Failure message and call log
```
{message}
```

## Steps recorded before the failure
{steps}

## Test data used in this run
```json
{test_data}
```
~~~~

The answer must match `JUDGEMENT_SCHEMA`: `locator_is_intended`, `expected_value_is_correct` (each true/false/null)
and a reason for each. The request uses structured output, `effort: medium`, `max_tokens: 4000` and the API's
server-side refusal fallback (`fallbacks: "default"`).

## What happens when AI is unavailable or answers badly

| Situation | 3A data generator | 3B triage |
|---|---|---|
| No `ANTHROPIC_API_KEY` | Faker (`id_ID` locale) generates the data, seeded with `RUN_ID`, so the same run ID always reproduces the same data. | Rules only. Steps 2b and 4 are marked "NOT reviewed" in the report. |
| API error (network, auth, rate limit) | The SDK has already retried transient errors, so we go straight to Faker with no extra retries. | Rules only; the reason is printed under the failure. |
| `stop_reason` is not `end_turn` (e.g. refusal, max tokens) | Counted as an invalid attempt. | Rules only. |
| Valid JSON that breaks our rules (wrong phone format, real-looking domain, name too long, unknown industry...) | Rejected by Pydantic; one retry with the error fed back; then Faker. | Rejected by Pydantic; rules only. |

Whatever the source, the data passes the **same** schema before any test uses it (the Faker output is validated too),
then gets the `QA<RUN_ID>` tag. The Allure report attaches the data actually used, its source
(`claude-haiku-4-5` or `faker-fallback`) and every attempt with its rejection reason.
`tests/unit/test_data_generator.py` and `tests/unit/test_triage.py` exercise every branch offline with a fake client.

## What AI is deliberately NOT allowed to do

- **Decide a verdict.** In triage, the code walks the evidence order from the brief and computes the verdict. Claude
  only answers two yes/no questions that rules cannot (is this the *intended* element, is the expected value right).
  It cannot override a rule match: if the failure is an exception, a locator that did not resolve, or a failed
  precondition, Claude is never called. *Why:* a model should not be the judge of whether a failure is real.
- **Touch tests or results.** Triage only reads `allure-results/` and writes `reports/triage_report.md`. It cannot
  edit, skip or weaken an assertion, change an expected value, or retry a test until it passes. Re-runs for the
  flakiness check go to a temporary directory and never replace the original result. A failing test stays failing.
- **File or close anything.** There is no Jira/GitHub integration. Every verdict is labelled a proposal for a human.
- **Invent dropdown values or IDs.** Industry is an enum of real options. Company type, language, address and branch
  are fixed constants. The KTP (national ID) number for the mobile form is generated in code (`synthetic_ktp`) and is
  never requested from a model.
- **Pick real-world contact data.** Emails must be on `*.example.com` (RFC 2606 reserved), so a shared environment never
  mails a real business.
- **See secrets.** Credentials are never put into a prompt. Maestro output is redacted before it reaches Allure,
  and the triage prompt only ever contains that redacted text.

## Token cost

- **3A:** one call per session, roughly 600 input and 250 output tokens, capped at `max_tokens=1024`. That's a
  fraction of a cent per run on Haiku. At most two calls if the first answer is rejected.
- **3B:** zero calls when rules decide (exceptions, unresolved locators, failed preconditions). Otherwise one call per
  remaining failure, with the failure message trimmed to 3,000 characters and only the failing test's function
  source (not the whole file). Typically 1-2k input tokens per call.
- No AI runs inside the assertions themselves, so model latency or outages never change a test result.

## Status at submission

- The offline behaviour (fallback, schema rejection, retries, rules-only triage) is covered by unit tests. It was the
  path used during development, before an API key was available.
- With the key set, the live 3A path generated the data for the evidence run: `claude-haiku-4-5`, accepted on the
  first attempt (run 665777: "PT Mitra Emas Kencana" with customer "Toko Perhiasan Bintang Mas"; run 907CC0:
  "PT Mitra Teknologi" / "Toko Komputer Sejahtera"). The Allure report attaches that data with `source: claude-haiku-4-5`.
- The live 3B path triaged the deliberately broken run in `evidence/triage_report.md`.
