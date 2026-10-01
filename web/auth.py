"""Log in once and save the session (cookies + localStorage) to auth/esuite_state.json.

Used by the session fixture in web/conftest.py. Can also be run by hand to refresh the
session or to watch the login flow:  python -m web.auth --headed
"""
import sys
import time

from playwright.sync_api import Browser, expect, sync_playwright

from config import settings
from web.pages.base_page import REDIRECT_TIMEOUT_MS
from web.pages.dashboard_page import DashboardPage
from web.pages.login_page import LoginPage


def save_storage_state(browser: Browser, reuse_if_fresh: bool = False) -> str:
    state = settings.STORAGE_STATE
    if reuse_if_fresh and state.exists() and time.time() - state.stat().st_mtime < settings.AUTH_MAX_AGE_MIN * 60:
        return str(state)

    if not settings.ESUITE_EMAIL or not settings.ESUITE_PASSWORD:
        raise RuntimeError("ESUITE_EMAIL / ESUITE_PASSWORD are not set - copy .env.example to .env")

    context = browser.new_context()
    try:
        page = context.new_page()
        LoginPage(page).open().login(settings.ESUITE_EMAIL, settings.ESUITE_PASSWORD)
        expect(DashboardPage(page).greeting).to_be_visible(timeout=REDIRECT_TIMEOUT_MS)
        settings.AUTH_DIR.mkdir(exist_ok=True)
        context.storage_state(path=settings.STORAGE_STATE)
    finally:
        context.close()
    return str(settings.STORAGE_STATE)


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless="--headed" not in sys.argv)
        print(f"saved {save_storage_state(browser)}")
        browser.close()
