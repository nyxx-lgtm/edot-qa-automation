import shutil

import pytest

from config import settings


def pytest_collection_modifyitems(items):
    for item in items:
        if "mobile" in item.path.parts:
            item.add_marker(pytest.mark.mobile)


@pytest.fixture(scope="session")
def maestro_ready():
    """Fail fast (not skip) with a clear message when the mobile toolchain is missing."""
    if not shutil.which(settings.MAESTRO_BIN):
        pytest.fail(f"Maestro CLI not found ({settings.MAESTRO_BIN!r}) - set MAESTRO_BIN in .env")


@pytest.fixture(scope="session")
def sfa_credentials():
    """The salesman used for login/customer tests.

    A company created by the web suite cannot log in to eWork until a Sales Admin sets the user
    up on the SFA side (see MOB-LOGIN-02), so these tests use the account the brief provides as a
    fallback. The README says so.
    """
    creds = {"EWORK_COMPANY_ID": settings.EWORK_COMPANY_ID, "EWORK_USERNAME": settings.EWORK_USERNAME,
             "EWORK_PASSWORD": settings.EWORK_PASSWORD}
    missing = [k for k, v in creds.items() if not v]
    if missing:
        pytest.fail(f"missing in .env: {', '.join(missing)}")
    return creds
