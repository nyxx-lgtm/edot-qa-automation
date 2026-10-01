# eDOT QA Automation - take-home (V4)

Web (eSuite) with Playwright + Pytest, mobile (eWork SFA) with Maestro + Pytest, one Allure report for both,
and AI inside the suite: generated test data (3A) and failure triage (3B).

- **Test cases (Phase 1):** [`docs/test_cases.xlsx`](docs/test_cases.xlsx) (built by `docs/build_test_cases.py`)
- **Product findings:** [`docs/FINDINGS.md`](docs/FINDINGS.md)
- **AI design, prompts and guardrails:** [`AI_USAGE.md`](AI_USAGE.md)
- **Evidence:** [`evidence/allure-full-run/index.html`](evidence/allure-full-run/index.html), a full run of web, mobile and
  unit tests, 52/52 passed, data generated live by Claude (run 665777). Download it and open it in a browser; it is a
  single self-contained file. Also [`evidence/triage_report.md`](evidence/triage_report.md), the live AI triage of a deliberately
  broken run (`QA_BREAK=wrong_element`), and that run's report in
  [`evidence/allure-deliberate-failure/index.html`](evidence/allure-deliberate-failure/index.html).

## What is covered

| ID | Scenario | Tier | Where |
|---|---|---|---|
| WEB-LOGIN-01 | Valid login -> "Welcome Back," | 1 | `web/tests/test_login.py` |
| WEB-LOGIN-02/03 | Wrong password / unregistered email -> exact messages | Negative | `web/tests/test_login.py` |
| WEB-COMP-01 | Register a company (3-step wizard) -> listed with its ID | 2 | `web/tests/test_company.py` + `registered_company` fixture |
| WEB-COMP-02 | Detail matches the input, field by field (UI **and** stored record) | 2 | `web/tests/test_company.py` |
| WEB-COMP-03/04/05 | Invalid email message, Next gated, 30-char name limit | Negative / 1 | `web/tests/test_company.py` |
| WEB-COMP-06 | Delete -> record gone (API 'company not found' + not in the account) | 2 | fixture teardown, `web/company_lifecycle.py` |
| MOB-LOGIN-01 | Salesman login -> dashboard | 1 | `mobile/flows/login_dashboard.yaml` |
| MOB-LOGIN-02 | **Handoff:** the user created by the web suite in its new company -> "Please contact Sales Admin." | Negative | `mobile/flows/login_refused.yaml` |
| MOB-CUST-01 | Submit gated on KTP, Register gated on signature | 1 | `mobile/flows/create_customer.yaml` |
| MOB-CUST-02 | Create a customer -> one list card holds our name, address, type, status, reg. number | 2 | `mobile/flows/create_customer.yaml` |

Tier 2 assertions carry a `# Tier 2:` comment in the code and the YAML.

### Honest notes

- **Mobile uses the fallback account from the brief** (its salesman user) for MOB-LOGIN-01 and MOB-CUST.
  The genuine handoff was built and runs every time. The web suite registers a company, adds a salesman user to it
  (Company User -> + Add User, branch Headquarter) and hands its credentials to the mobile suite. But eWork refuses
  that user with "Failed to login. Please contact Sales Admin.": a brand-new company's user is not set up as a
  salesman on the SFA side. MOB-LOGIN-02 asserts exactly that, so the handoff is tested up to where the product allows.
- **Customer phone, email and contact person are not asserted** after creation. A registration "Waiting for Approval"
  has no detail screen, and the app shows none of those three fields anywhere. Name, street address, customer type,
  status and registration number are asserted together on one list card.
- **Customers cannot be deleted** from eWork. Every customer the suite registers is tagged `QA<RUN_ID>` and recorded with
  its registration number in `handoff/created_customers.json`. During development and the evidence run the suite
  registered CUST-00283, CUST-00284, CUST-00285 and CUST-00286 (names ending QAA0F2A5, QA8A9756, QAC95EA1, QA665777).
- **Companies are always cleaned up.** Each one is written to a ledger before Register is clicked, deleted at session end,
  and proven gone. `python -m web.company_lifecycle --cleanup` removes anything a crashed run left behind.

## Project layout

```
ai/                 3A data generator, 3B triage, schemas, every prompt (prompts.py)
config/             settings (.env), dropdown constants captured from the live apps
web/pages/          page objects - all locators live here
web/tests/          web tests (no raw selectors)
web/auth.py         log in once, save storage_state
web/company_lifecycle.py   register / add user / delete / cleanup ledger
mobile/flows/       Maestro flows; subflows/ = login, dashboard check, address picker (runFlow)
mobile/maestro.py   pytest -> Maestro wrapper (env vars, redaction, Allure evidence)
mobile/tests/       pytest wrappers for the flows
tests/unit/         offline tests for the AI modules and the flow files
conftest.py         session fixtures shared by web and mobile
docs/               test case sheet, findings
```

## Setup

Prerequisites: Python 3.11+, Java 17+ (Allure and Maestro), Node.js (for the Allure CLI), Android Studio with an emulator.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
playwright install chromium
npm install -g allure-commandline
copy .env.example .env            # cp on macOS/Linux, then fill in .env
```

`.env` holds the eSuite and eWork credentials, the optional `ANTHROPIC_API_KEY` and `MAESTRO_BIN`.
It is git-ignored. Nothing secret is in the repository.

### Mobile toolchain

1. **Maestro CLI:** download `maestro.zip` from the [Maestro releases](https://github.com/mobile-dev-inc/maestro/releases),
   unzip it, and set `MAESTRO_BIN` in `.env` to `...\maestro\bin\maestro.bat` (Windows) or `maestro` (macOS/Linux, or WSL).
   Check with `maestro --version` (developed with 2.11.0).
2. **Emulator:** an Android 14+ image **with Google Play**. Install **eWork - SFA** (`id.edot.ework`, developed against 2.5.0)
   from the Play Store, then start the emulator.
   `adb devices` must list it (adb is in `<Android SDK>/platform-tools`).
3. **Selectors** were taken with `maestro hierarchy`. Do not set a mock location: eWork blocks "fake GPS".

## Running

```bash
pytest tests/unit                 # offline: AI modules + flow files (no network, no key)
pytest web                        # web suite (headless Chromium)
pytest web --headed               # watch it
pytest mobile                     # mobile suite (needs the emulator; also registers a company for the handoff)
pytest                            # everything, one Allure run
pytest -n 4 web/tests/test_login.py   # parallel (pytest-xdist)
```

A full run takes about 25 minutes, most of it the mobile customer flow. The New Customer List is shared by every
candidate and the newest entry is at the bottom of 280+ cards.

### Allure report

```bash
allure generate allure-results -o allure-report --clean
allure open allure-report
```

Each test shows its steps. Failures carry a screenshot and the URL; mobile tests carry the Maestro output (passwords
redacted), the screen recording and the flow's screenshots. The session attaches the generated test data and its source.

In the committed evidence report, the 12-minute recording of MOB-CUST-02 (88 MB) is replaced by a note,
because GitHub limits files to 100 MB. The recording itself is published as a release asset. Nothing else was changed.

### AI failure triage (3B)

```bash
python -m ai.triage                  # reads allure-results, re-runs each failure twice, writes reports/triage_report.md
python -m ai.triage --reproduce 0    # no re-runs
```

**Deliberately failing run** (evidence for the reviewer):

```bash
set QA_BREAK=wrong_element           # Windows cmd;  $env:QA_BREAK="wrong_element" in PowerShell;  export on macOS/Linux
pytest web/tests/test_company.py
python -m ai.triage
```

`QA_BREAK=wrong_element` points the detail page's email locator at the Company Name input. It is a real element,
so only the AI judgement catches it. `QA_BREAK=missing_locator` looks for a message that does not exist, which the
rules catch.

### Cleanup

```bash
python -m web.company_lifecycle --cleanup
```

## Design decisions

- **Locators** (no `data-testid` exists anywhere): role + accessible name, then a stable attribute (`placeholder` / `name`),
  then label-anchored CSS for the Radix dropdowns, and text only where an element has nothing else. Each text locator
  carries a comment saying why. On mobile: resource `id` first, then text. There are no coordinate taps; the signature is
  drawn by a swipe anchored on the `signature_view` element.
- **No sleeps.** Playwright `expect` / auto-waiting and Maestro `extendedWaitUntil` / `waitForAnimationToEnd` only.
  The one polling loop (`wait_until_accessible`) reloads the page and is bounded.
- **One login per session** via `storage_state`; the login tests use a separate clean context because login is what they test.
- **Assertions use our own data, never global counts.** The eSuite account is shared by every candidate.
- **API checks where the UI hides data:** dropdowns truncate at 20 characters, so WEB-COMP-02 also checks the record the
  Manage page loads. API bodies are re-requested with the page's own auth header, because Chrome discards intercepted
  bodies when the app navigates.
- **Data:** AI-generated, schema-validated, tagged `QA<RUN_ID>`, emails on `*.example.com`. `RUN_ID=<id>` reproduces a
  fallback run's data exactly.
- **Credentials** reach Maestro as `MAESTRO_*` environment variables, so they never appear on the command line or in YAML.
  `tests/unit/test_flow_files.py` fails if a value from `.env` ever appears in a flow.

## CI

`.github/workflows/web.yml` runs the web suite headless on every push, then the triage, and publishes the Allure report
(GitHub Pages) plus the triage report as artifacts. Repository secrets: `ESUITE_EMAIL`, `ESUITE_PASSWORD`, and
optionally `ANTHROPIC_API_KEY`.
