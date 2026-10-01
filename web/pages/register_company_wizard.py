import allure
from playwright.sync_api import expect

from ai.schemas import CompanyData
from config import settings
from config.test_constants import ADDRESS_CASCADE, BRANCH_NAME, COMPANY_TYPE, LANGUAGE
from web.pages.base_page import BasePage

# Registration provisions a whole workspace; it regularly takes 10+ seconds.
REGISTER_TIMEOUT_MS = 60_000


class RegisterCompanyWizard(BasePage):
    """Companies -> + Add Company: 1/3 company, 2/3 legal documents, 3/3 branch."""

    def __init__(self, page):
        super().__init__(page)
        # The inputs have no name, id or linked label; the placeholder is the stable attribute.
        self.company_name = page.get_by_placeholder("Input Company Name")
        self.email = page.get_by_placeholder("Input Email")
        self.phone = page.get_by_placeholder("Input Phone")
        self.street_address = page.get_by_placeholder("Input Address")
        self.branch_name = page.get_by_placeholder("Input Branch Name")
        self.next_button = page.get_by_role("button", name="Next")
        self.register_button = page.get_by_role("button", name="Register")
        self.copy_company_address = page.get_by_role("button", name="Fill in with the same data from the Company record")
        self.agree_terms = page.get_by_role("checkbox")
        # Text locators (last resort): headings and messages carry no role/id/test id.
        self.step_company = page.get_by_text("Register Company", exact=True)
        self.step_legal = page.get_by_text("Register Legal", exact=True)
        self.step_branch = page.get_by_text("Create Your Branch", exact=True)
        self.invalid_email_error = page.get_by_text("Please provide a valid email address")
        if settings.QA_BREAK == "missing_locator":  # deliberate defect for the triage demo
            self.invalid_email_error = page.get_by_text("Please enter a valid email")

    def fill_company_step(self, company: CompanyData, email: str | None = None):
        with allure.step("Step 1/3 - Register Company"):
            expect(self.step_company).to_be_visible()
            self.company_name.fill(company.legal_name)
            self.email.fill(email if email is not None else company.email)
            self.phone.fill(company.phone)
            self.choose("Industry Type", company.industry)
            self.choose("Company Type", COMPANY_TYPE)
            self.choose("Language", LANGUAGE)
            self.street_address.fill(company.street_address)
            self.fill_address_cascade()

    def fill_address_cascade(self):
        self.choose("Country", ADDRESS_CASCADE["country"])
        self.choose("Province", ADDRESS_CASCADE["province"], search=True)
        self.choose("City", ADDRESS_CASCADE["city"], search=True)
        self.choose("District", ADDRESS_CASCADE["district"], search=True)
        self.choose("Sub District", ADDRESS_CASCADE["sub_district"], search=True)
        # Postal Code is derived from the Sub District and is read-only.
        expect(self.field_combobox("Postal Code")).to_have_text(ADDRESS_CASCADE["postal_code"])

    def go_next(self):
        self.next_button.click()

    def skip_legal_step(self):
        with allure.step("Step 2/3 - Register Legal (optional, skipped)"):
            expect(self.step_legal).to_be_visible()
            self.next_button.click()

    def fill_branch_step(self):
        with allure.step("Step 3/3 - Create Your Branch (same address as company)"):
            expect(self.step_branch).to_be_visible()
            # The branch name is sometimes pre-filled asynchronously and sometimes not.
            # Typing it ourselves makes the step deterministic and reveals the copy button.
            self.branch_name.fill(BRANCH_NAME)
            self.copy_company_address.click()
            self.agree_terms.click()
            expect(self.agree_terms).to_have_attribute("aria-checked", "true")

    def register(self):
        with allure.step("Click Register"):
            expect(self.register_button).to_be_enabled()
            self.register_button.click()
            # Success = leaving the wizard for the Companies list.
            self.page.wait_for_url("**/companies", timeout=REGISTER_TIMEOUT_MS)
