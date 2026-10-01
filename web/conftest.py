import pytest

from config.settings import VIEWPORT


def pytest_collection_modifyitems(items):
    for item in items:
        if "web" in item.path.parts:
            item.add_marker(pytest.mark.web)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, esuite_storage_state):
    # Every `page` fixture from pytest-playwright starts already logged in.
    return {**browser_context_args, "storage_state": esuite_storage_state, "viewport": VIEWPORT}


@pytest.fixture
def anon_page(browser):
    """A clean, logged-out page - only for tests whose subject is the login itself."""
    context = browser.new_context(viewport=VIEWPORT)
    page = context.new_page()
    yield page
    context.close()
