"""Every prompt the suite sends to a model lives here, verbatim, so AI_USAGE.md can quote it."""

DATA_SYSTEM_PROMPT = (
    "You generate realistic, fictional Indonesian business test data for an automated QA suite. "
    "Reply with JSON only, matching the provided schema exactly."
)

DATA_USER_PROMPT = """Generate one company and one customer for a B2B sales app in Indonesia.

Rules:
- company.legal_name: a plausible Indonesian legal entity, starting with "PT " or "CV ", 1-3 short words after the prefix, max 21 characters in total (e.g. "PT Sinar Jaya Niaga"). No real, well-known brands.
- company.industry: pick the option that best fits the company name.
- company.street_address and customer.street_address: a street line in Jakarta, e.g. "Jl. Wolter Monginsidi No. 12". No city, province or postal code - those are chosen separately.
- phone numbers: Indonesian mobile without the country code or leading 0 (the form shows +62 already), digits only, starting with 8, 9-12 digits in total, e.g. "81234567890".
- emails: must use a subdomain of example.com derived from the company, e.g. "sales@sinarjaya.example.com". Never use a real domain.
- customer.name: a retail shop (toko) that would buy from this company, max 30 characters.
- customer.contact_person: the shop owner's full Indonesian name, max 30 characters.
- The company, its industry and the customer should make sense together."""

# Appended on a retry so the model sees why its previous answer was rejected.
DATA_RETRY_SUFFIX = "\n\nYour previous answer was rejected by schema validation:\n{error}\nFix those fields and answer again."


TRIAGE_SYSTEM_PROMPT = (
    "You review one failed UI test for a QA engineer. You answer two narrow questions with evidence "
    "quoted from the material you are given. You never suggest changing, weakening or skipping the "
    "test's assertions, and you never decide the final verdict - a human does. Reply with JSON only."
)

TRIAGE_USER_PROMPT = """A rule engine already established: the failure is an assertion (not an exception), \
the locator resolved, and every earlier step and fixture passed. Two questions remain.

Q1 - locator_is_intended: Did the assertion's locator resolve to the element the test meant to check? \
Compare what the test intends (its title, the page-object attribute name, the expected value) with the \
element the call log says was resolved (tag, placeholder, text). Answer null if there was no locator.

Q2 - expected_value_is_correct: Is the expected value in the assertion the right value according to the \
test case and the test data that was actually used? Answer null if you cannot tell from the material.

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
```"""
