import allure
from playwright.sync_api import expect

from config.test_constants import ADDRESS_CASCADE, COMPANY_TYPE, LANGUAGE
from web.pages.base_page import as_displayed
from web.pages.companies_page import CompaniesPage
from web.pages.company_detail_page import CompanyDetailPage
from web.pages.register_company_wizard import RegisterCompanyWizard


@allure.feature("Web - Company")
class TestCompany:

    @allure.title("WEB-COMP-01 Registered company is listed with its ID")
    def test_registered_company_is_listed(self, page, registered_company):
        companies = CompaniesPage(page).open()

        card = companies.card(registered_company.name)
        # Tier 2: exactly one card with our exact name, carrying the ID eSuite assigned.
        expect(card).to_have_count(1)
        expect(card).to_contain_text(registered_company.company_id)
        expect(card).to_contain_text("Active")

    @allure.title("WEB-COMP-02 Company detail matches the registration input field by field")
    def test_company_detail_matches_input(self, page, registered_company, generated_data):
        company = generated_data.company
        detail = CompanyDetailPage(page)
        stored = detail.open_and_read(registered_company.manage_url)[1]["data"]
        detail.wait_loaded(company.legal_name)

        # Tier 2: what eSuite stored, in full (the UI truncates long dropdown values).
        with allure.step("Stored record (company API)"):
            assert stored["company_name"] == company.legal_name
            assert stored["email"] == company.email
            assert stored["phone"] == f"+62{company.phone}"
            assert stored["company_type"] == COMPANY_TYPE.lower()
            assert stored["address"]["street_address"] == company.street_address
            assert stored["address"]["province"]["name"] == ADDRESS_CASCADE["province"]
            assert stored["address"]["city"]["name"] == ADDRESS_CASCADE["city"]
            assert stored["address"]["postal_code"] == ADDRESS_CASCADE["postal_code"]

        # Tier 2: every value shown must equal what was typed/chosen in the wizard.
        with allure.step("Identity"):
            expect(detail.company_name).to_have_value(company.legal_name)
            expect(detail.company_id).to_have_value(registered_company.company_id)
            # Dropdowns show 20 characters max; the full value is not exposed in the DOM.
            expect(detail.dropdown_value("Industry Type")).to_have_text(as_displayed(company.industry))
            expect(detail.dropdown_value("Company Type")).to_have_text(COMPANY_TYPE)
        with allure.step("Contact"):
            expect(detail.email).to_have_value(company.email)
            expect(detail.mobile_number).to_have_value(company.phone)
        with allure.step("Address"):
            expect(detail.company_address).to_have_value(company.street_address)
            expect(detail.dropdown_value("Province")).to_have_text(ADDRESS_CASCADE["province"])
            expect(detail.dropdown_value("City")).to_have_text(ADDRESS_CASCADE["city"])
            expect(detail.dropdown_value("District")).to_have_text(ADDRESS_CASCADE["district"])
            expect(detail.dropdown_value("Sub District")).to_have_text(ADDRESS_CASCADE["sub_district"])
            expect(detail.dropdown_value("Postal Code")).to_have_text(ADDRESS_CASCADE["postal_code"])

    @allure.title("WEB-COMP-03 Invalid email blocks step 1 with 'Please provide a valid email address'")
    def test_invalid_email_is_rejected(self, page, generated_data):
        CompaniesPage(page).open().start_registration()
        wizard = RegisterCompanyWizard(page)
        wizard.fill_company_step(generated_data.company, email="not-an-email")

        wizard.go_next()

        # Negative: the specific message, and we are still on step 1 (nothing was created).
        expect(wizard.invalid_email_error).to_be_visible()
        expect(wizard.step_company).to_be_visible()
        expect(wizard.step_legal).not_to_be_visible()

    @allure.title("WEB-COMP-04 Next stays disabled until step 1 is complete")
    def test_next_disabled_until_step_is_valid(self, page, generated_data):
        company = generated_data.company
        CompaniesPage(page).open().start_registration()
        wizard = RegisterCompanyWizard(page)
        expect(wizard.next_button).to_be_disabled()

        # Everything except the street address.
        wizard.company_name.fill(company.legal_name)
        wizard.email.fill(company.email)
        wizard.phone.fill(company.phone)
        wizard.choose("Industry Type", company.industry)
        wizard.choose("Company Type", COMPANY_TYPE)
        wizard.choose("Language", LANGUAGE)
        wizard.fill_address_cascade()
        expect(wizard.next_button).to_be_disabled()

        wizard.street_address.fill(company.street_address)
        expect(wizard.next_button).to_be_enabled()

    @allure.title("WEB-COMP-05 Company Name refuses input longer than 30 characters")
    def test_company_name_is_limited_to_30_characters(self, page):
        CompaniesPage(page).open().start_registration()
        wizard = RegisterCompanyWizard(page)

        wizard.company_name.fill("PT Tiga Puluh Karakter Pas QA1")      # exactly 30
        expect(wizard.company_name).to_have_value("PT Tiga Puluh Karakter Pas QA1")

        wizard.company_name.fill("PT Tiga Puluh Satu Karakter QA12")   # 32
        # Negative: the over-long value is refused and the previous value is kept.
        # There is no error message to assert - the field gives no feedback at all (BUG-02).
        expect(wizard.company_name).to_have_value("PT Tiga Puluh Karakter Pas QA1")
