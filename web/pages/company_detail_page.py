import re

import allure
from playwright.sync_api import Response, expect

from config import settings
from web.pages.base_page import BasePage

# The Manage page loads the company from GET /api/v1/company/<24-hex id>.
DETAIL_API = re.compile(r"/api/v1/company/[0-9a-f]{24}$")


class CompanyDetailPage(BasePage):
    """Companies -> Manage -> Company Details (an editable profile form)."""

    def __init__(self, page):
        super().__init__(page)
        # Placeholders are the only stable attributes on these inputs (no name/id/test id).
        self.company_name = page.get_by_placeholder("Input Company Name")
        self.company_id = page.get_by_placeholder("Input Company ID")
        self.email = page.get_by_placeholder("Input Email")
        if settings.QA_BREAK == "wrong_element":  # deliberate defect for the triage demo
            self.email = page.get_by_placeholder("Input Company Name")
        self.mobile_number = page.get_by_placeholder("Input Mobile Number")
        self.company_address = page.get_by_placeholder("Input Company Address")
        self.delete_button = page.get_by_role("button", name="Delete", exact=True)
        self.delete_dialog = page.get_by_role("dialog")

    def open(self, manage_url: str) -> Response:
        """Open the page and return the company API response it loaded."""
        with self.page.expect_response(lambda r: DETAIL_API.search(r.url.split("?")[0])) as info:
            self.page.goto(manage_url)
        return info.value

    def open_and_read(self, manage_url: str) -> tuple[int, dict]:
        """Status and JSON body of the company API behind the page (see BasePage.refetch)."""
        api = self.refetch(self.open(manage_url))
        return api.status, api.json()

    def wait_loaded(self, company_name: str):
        # The form renders empty first and is populated from the API afterwards.
        expect(self.company_name).to_have_value(company_name)
        return self

    def dropdown_value(self, label: str):
        """Selected dropdown values are shown as the combobox text."""
        return self.field_combobox(label)

    def delete_company(self):
        with allure.step("Delete company (confirm dialog)"):
            self.delete_button.click()
            expect(self.delete_dialog).to_be_visible()
            confirm = self.delete_dialog.get_by_role("button", name="Confirm")
            # Confirm stays disabled until "I understand & agree to delete" is ticked.
            expect(confirm).to_be_disabled()
            self.delete_dialog.get_by_role("checkbox").click()
            confirm.click()
            self.page.wait_for_url("**/companies")
