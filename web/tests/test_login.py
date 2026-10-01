import allure
from playwright.sync_api import expect

from config import settings
from web.pages.base_page import REDIRECT_TIMEOUT_MS
from web.pages.dashboard_page import DashboardPage
from web.pages.login_page import LoginPage


@allure.feature("Web - Login")
class TestLogin:

    @allure.title("WEB-LOGIN-01 Valid credentials land on the dashboard")
    def test_valid_login_shows_dashboard(self, anon_page):
        login = LoginPage(anon_page).open()

        login.login(settings.ESUITE_EMAIL, settings.ESUITE_PASSWORD)

        # Tier 1: display only - the greeting proves we are on the dashboard.
        expect(DashboardPage(anon_page).greeting).to_be_visible(timeout=REDIRECT_TIMEOUT_MS)
        expect(anon_page).to_have_url(f"{settings.ESUITE_BASE_URL}/")

    @allure.title("WEB-LOGIN-02 Wrong password shows 'Incorrect password'")
    def test_wrong_password_shows_error(self, anon_page):
        login = LoginPage(anon_page).open()

        login.login(settings.ESUITE_EMAIL, "WrongPassword123")

        # Negative: assert the specific message, not just that we are still on the login page.
        expect(login.incorrect_password_error).to_be_visible(timeout=REDIRECT_TIMEOUT_MS)
        expect(DashboardPage(anon_page).greeting).not_to_be_visible()

    @allure.title("WEB-LOGIN-03 Unregistered email shows 'Email Not Registered'")
    def test_unregistered_email_shows_prompt(self, anon_page):
        login = LoginPage(anon_page).open()
        email = f"not.registered.{settings.RUN_ID.lower()}@example.com"

        login.submit_email(email)

        # Negative: the specific dialog, and it echoes the email we typed.
        expect(login.email_not_registered_title).to_be_visible()
        expect(login.email_not_registered_hint).to_be_visible()
        expect(login.entered_email(email)).to_be_visible()
        expect(login.password_input).not_to_be_visible()
