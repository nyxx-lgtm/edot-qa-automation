from playwright.sync_api import expect

from config import settings
from web.pages.base_page import REDIRECT_TIMEOUT_MS, BasePage


class LoginPage(BasePage):
    """eDOT Account Center (cronus.edot.id): three screens - method, email, password."""

    def __init__(self, page):
        super().__init__(page)
        self.use_email_button = page.get_by_role("button", name="Use Email or Username")
        # The inputs have no label association or test id; `name` is the most stable attribute.
        self.username_input = page.locator("input[name='username']")
        # The email screen also renders a hidden input[name='password']; type narrows it to the real one.
        self.password_input = page.locator("input[name='password'][type='password']")
        self.login_button = page.get_by_role("button", name="Log In")
        # Text locators (last resort): these messages have no role, id or test id in the DOM.
        self.incorrect_password_error = page.get_by_text("Incorrect password")
        self.email_not_registered_title = page.get_by_text("Email Not Registered", exact=True)
        self.email_not_registered_hint = page.get_by_text("You can continue by creating new account with this email")

    def entered_email(self, email: str):
        """The 'Email Not Registered' dialog echoes the email that was typed (plain text, no role)."""
        return self.page.get_by_text(email, exact=True)

    def open(self):
        # eSuite redirects unauthenticated users to the Account Center.
        self.page.goto(settings.ESUITE_BASE_URL)
        expect(self.use_email_button).to_be_visible(timeout=REDIRECT_TIMEOUT_MS)
        return self

    def submit_email(self, email: str):
        self.use_email_button.click()
        self.username_input.fill(email)
        self.login_button.click()

    def submit_password(self, password: str):
        self.password_input.fill(password)
        self.login_button.click()

    def login(self, email: str, password: str):
        self.submit_email(email)
        self.submit_password(password)
