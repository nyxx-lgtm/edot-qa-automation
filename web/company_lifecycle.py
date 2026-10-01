"""Create and delete the run's company. Shared by the pytest fixture and the cleanup CLI.

Every company we register is written to a local ledger (handoff/created_companies.json)
*before* clicking Register, so even a crashed run leaves a record of what to clean up:
    python -m web.company_lifecycle --cleanup
"""
import json
import re
import secrets
import sys
import time
from dataclasses import asdict, dataclass

import allure
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from ai.schemas import CompanyData
from config import settings
from config.test_constants import BRANCH_NAME
from web.pages.companies_page import CompaniesPage
from web.pages.company_detail_page import CompanyDetailPage
from web.pages.company_user_page import CompanyUserPage
from web.pages.register_company_wizard import RegisterCompanyWizard

LEDGER = settings.ROOT_DIR / "handoff" / "created_companies.json"
# Right after registration the login token does not list the new company yet, so the
# Manage page cannot load it. eSuite refreshes the grant on its own within a minute or two.
ACCESS_TIMEOUT_S = 180


@dataclass
class RegisteredCompany:
    name: str
    company_id: str
    manage_url: str


# ---------- ledger ----------

def _ledger() -> list[dict]:
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else []


def _save_ledger(entries: list[dict]):
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(entries, indent=2))


def _ledger_upsert(entry: dict):
    _save_ledger([e for e in _ledger() if e["name"] != entry["name"]] + [entry])


def _ledger_remove(name: str):
    _save_ledger([e for e in _ledger() if e["name"] != name])


# ---------- create ----------

def register_company(page: Page, company: CompanyData) -> RegisteredCompany:
    CompaniesPage(page).open().start_registration()
    wizard = RegisterCompanyWizard(page)
    wizard.fill_company_step(company)
    wizard.go_next()
    wizard.skip_legal_step()
    wizard.fill_branch_step()
    _ledger_upsert({"name": company.legal_name})
    wizard.register()

    CompaniesPage(page).open().open_manage(company.legal_name)
    page.wait_for_url("**/manage-companies/**")
    manage_url = page.url
    registered = RegisteredCompany(company.legal_name, re.search(r"cid=(\d+)", manage_url).group(1), manage_url)
    _ledger_upsert(asdict(registered))

    wait_until_accessible(page, registered)
    settings.HANDOFF_FILE.write_text(json.dumps(asdict(registered), indent=2))
    allure.attach(json.dumps(asdict(registered), indent=2), name="registered company",
                  attachment_type=allure.attachment_type.JSON)
    return registered


def wait_until_accessible(page: Page, company: RegisteredCompany):
    """Reload the Manage page until the API serves our company and the form shows it (bounded)."""
    detail = CompanyDetailPage(page)
    deadline = time.monotonic() + ACCESS_TIMEOUT_S
    attempt = 0
    with allure.step(f"Wait until eSuite serves '{company.name}' (max {ACCESS_TIMEOUT_S}s)"):
        while True:
            attempt += 1
            try:
                status, body = detail.open_and_read(company.manage_url)
                served = status == 200 and (body.get("data") or {}).get("company_name") == company.name
                last = f"HTTP {status}"
            except PlaywrightError as e:  # the page may not call the API at all while access is missing
                served, last = False, type(e).__name__
            if served:
                try:
                    # The API answering is not enough: on slower networks (CI) the form can lag behind it.
                    detail.wait_loaded(company.name)
                    allure.attach(f"served after {attempt} load(s)", name="access wait",
                                  attachment_type=allure.attachment_type.TEXT)
                    return
                except AssertionError:
                    last = "API served the company but the form stayed empty"
            if time.monotonic() > deadline:
                raise AssertionError(f"'{company.name}' not shown on its Manage page "
                                     f"{ACCESS_TIMEOUT_S}s after registration (last: {last})")


# ---------- handoff user for the mobile suite ----------

@dataclass
class HandoffUser:
    company_id: str
    username: str
    password: str


def add_sfa_user(page: Page, company: RegisteredCompany) -> HandoffUser:
    """Create a salesman user in the run's company so the mobile suite can try to log in with it.

    The password is generated for this run only and written to the git-ignored handoff file.
    It never goes to Allure: only the username and company ID are attached.
    """
    tag = company.name.rsplit(" ", 1)[-1].lower()           # e.g. "qa7f3a2b"
    user = HandoffUser(company.company_id, f"sales_{tag}", "Qa!" + secrets.token_urlsafe(12))
    CompanyUserPage(page).open(company.manage_url).add_user(
        name=f"Salesman {tag.upper()}", username=user.username,
        email=f"{user.username}@handoff.example.com", phone="81" + f"{int(tag[2:], 36) % 10**9:09d}",
        password=user.password, branch=BRANCH_NAME)

    settings.HANDOFF_USER_FILE.write_text(json.dumps(asdict(user), indent=2))
    allure.attach(json.dumps({"company_id": user.company_id, "username": user.username}, indent=2),
                  name="handoff user (password withheld)", attachment_type=allure.attachment_type.JSON)
    return user


# ---------- delete ----------

def delete_company(page: Page, company: RegisteredCompany):
    """Delete via Manage and prove it is gone (Tier 2: a delete asserts the record is gone)."""
    detail = CompanyDetailPage(page)
    detail.open(company.manage_url)
    detail.wait_loaded(company.name).delete_company()

    with allure.step(f"Verify '{company.name}' ({company.company_id}) is gone"):
        status, body = detail.open_and_read(company.manage_url)
        allure.attach(f"HTTP {status}: {body}", name="company API after delete",
                      attachment_type=allure.attachment_type.TEXT)
        # Tier 2: the company record itself is no longer served. eSuite answers either
        # 404 or 500 with this message for a deleted company (BUG-03), so the message is checked.
        assert status >= 400, f"company API still serves the company after delete (HTTP {status})"
        assert body.get("message") == "company not found", f"unexpected body: {body}"
        # Tier 2: and it is no longer one of the account's companies.
        assert company.company_id not in CompaniesPage(page).account_company_ids()

    # Not asserted: the Companies card list. It is built from the login token's workspace
    # list and keeps showing a deleted company as Active until the next login (BUG-01).
    _ledger_remove(company.name)


def delete_if_registered(page: Page, name: str):
    """Best effort after a failed registration: delete the company if it got as far as a URL."""
    entry = next((e for e in _ledger() if e["name"] == name and "manage_url" in e), None)
    if entry and detail_status(page, RegisteredCompany(**entry)) != 404:
        delete_company(page, RegisteredCompany(**entry))


def cleanup_ledger():
    """Delete everything a previous run left in the ledger (e.g. after a crash)."""
    entries = _ledger()
    if not entries:
        print("ledger empty - nothing to clean up")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(storage_state=str(settings.STORAGE_STATE), viewport=settings.VIEWPORT)
        page = context.new_page()
        for entry in entries:
            if "manage_url" not in entry:
                # Crashed between Register and reading the URL: find it through the list.
                companies = CompaniesPage(page).open()
                if companies.card(entry["name"]).count() == 0:
                    print(f"NOT FOUND in list - check manually: {entry['name']}")
                    continue
                companies.open_manage(entry["name"])
                page.wait_for_url("**/manage-companies/**")
                entry = {**entry, "manage_url": page.url, "company_id": re.search(r"cid=(\d+)", page.url).group(1)}
            company = RegisteredCompany(**entry)
            if detail_status(page, company) >= 400:
                print(f"already gone: {company.name}")
                _ledger_remove(company.name)
                continue
            delete_company(page, company)
            print(f"deleted: {company.name} ({company.company_id})")
        browser.close()


def detail_status(page: Page, company: RegisteredCompany) -> int:
    return CompanyDetailPage(page).open(company.manage_url).status


if __name__ == "__main__" and "--cleanup" in sys.argv:
    cleanup_ledger()
