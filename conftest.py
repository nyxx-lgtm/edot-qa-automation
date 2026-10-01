"""Session fixtures shared by web and mobile: test data, login state, the run's company."""
import allure
import pytest

from ai.data_generator import generate_test_data
from config.settings import VIEWPORT
from web.auth import save_storage_state
from web.company_lifecycle import add_sfa_user, delete_company, delete_if_registered, register_company


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    # Exposes item.rep_setup / rep_call / rep_teardown to fixtures and hooks.
    setattr(item, f"rep_{report.when}", report)

    # Screenshot while the page is still open (fixture teardown has not run yet).
    if report.when == "call" and report.failed:
        for name in ("page", "anon_page"):
            page = item.funcargs.get(name)
            if page is not None and not page.is_closed():
                _attach_page(page, f"failure screenshot ({name})")


def _attach_page(page, name):
    allure.attach(page.screenshot(full_page=True), name=name, attachment_type=allure.attachment_type.PNG)
    allure.attach(page.url, name=f"{name} - url", attachment_type=allure.attachment_type.TEXT)


@pytest.fixture(scope="session")
def generated_data():
    """AI (or fallback) test data, generated once per session and attached to Allure."""
    result = generate_test_data()
    allure.attach(result.to_report(), name=f"test data - source: {result.source}",
                  attachment_type=allure.attachment_type.JSON)
    return result.data


@pytest.fixture(scope="session")
def esuite_storage_state(browser):
    """Log in once per session (or reuse a fresh saved session); tests share the state."""
    try:
        return save_storage_state(browser, reuse_if_fresh=True)
    except RuntimeError as e:
        pytest.fail(str(e))


@pytest.fixture(scope="session")
def registered_company(browser, esuite_storage_state, generated_data):
    """Register this run's company once; delete it (and prove it is gone) at session end.

    Session scope lets the mobile suite log into the same company before cleanup runs.
    """
    context = browser.new_context(storage_state=esuite_storage_state, viewport=VIEWPORT)
    page = context.new_page()
    try:
        with allure.step(f"Register company '{generated_data.company.legal_name}'"):
            company = register_company(page, generated_data.company)
    except Exception:
        _attach_page(page, "company registration failed")
        try:
            delete_if_registered(page, generated_data.company.legal_name)
        finally:
            context.close()
        raise  # anything left is still in the ledger: python -m web.company_lifecycle --cleanup

    yield company

    try:
        delete_company(page, company)
    except Exception:
        _attach_page(page, "company cleanup failed")
        raise
    finally:
        context.close()


@pytest.fixture(scope="session")
def handoff_user(browser, esuite_storage_state, registered_company):
    """A salesman user in this run's company - the web -> mobile handoff. Deleted with the company."""
    context = browser.new_context(storage_state=esuite_storage_state, viewport=VIEWPORT)
    page = context.new_page()
    try:
        return add_sfa_user(page, registered_company)
    except Exception:
        _attach_page(page, "handoff user creation failed")
        raise
    finally:
        context.close()
