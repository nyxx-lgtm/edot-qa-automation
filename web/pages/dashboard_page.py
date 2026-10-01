from config import settings
from web.pages.base_page import BasePage


class DashboardPage(BasePage):
    def __init__(self, page):
        super().__init__(page)
        # Text locator (last resort): the greeting is a bare <span> with no role or test id.
        self.greeting = page.get_by_text("Welcome Back,", exact=True)
        self.companies_nav = page.get_by_role("link", name="Companies", exact=True)

    def open(self):
        self.page.goto(settings.ESUITE_BASE_URL)
        return self
