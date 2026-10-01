import re

import allure

from config import settings
from web.pages.base_page import BasePage


class CompaniesPage(BasePage):
    URL = f"{settings.ESUITE_BASE_URL}/companies"

    def __init__(self, page):
        super().__init__(page)
        self.add_company_button = page.get_by_role("button", name="+ Add Company")
        # Account menu in the header, e.g. "itqaedot 569 Companies".
        self.account_menu = page.get_by_role("button", name=re.compile(r"\d+ Companies"))

    def open(self):
        with allure.step("Open Companies"):
            self.page.goto(self.URL)
            # The list renders after its API call; wait for real cards, not just the page shell,
            # otherwise "our card is absent" could be read before the list exists.
            self.cards.first.wait_for()
        return self

    @property
    def cards(self):
        # Cards have no role or test id; they are the bordered boxes in the active tab.
        return self.page.locator("[role=tabpanel] div.rounded-lg.border")

    def card(self, company_name: str):
        # Narrowed to the card whose name text is exactly ours (names carry a unique run tag).
        return self.cards.filter(has=self.page.get_by_text(company_name, exact=True))

    def account_company_ids(self) -> set[str]:
        """Company IDs the account owns, from the API behind the header count (not the card list)."""
        with self.page.expect_response(lambda r: r.url.split("?")[0].endswith("/api/v1/company")) as info:
            self.page.goto(self.URL)
        return {c["account_center_company_id"] for c in self.refetch(info.value).json()["data"]}

    def start_registration(self):
        with allure.step("Click + Add Company"):
            self.add_company_button.click()

    def open_manage(self, company_name: str):
        with allure.step(f"Open Manage for {company_name}"):
            self.card(company_name).get_by_role("button", name="Manage").click()
