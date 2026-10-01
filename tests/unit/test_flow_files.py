"""Offline guard: every Maestro flow is valid YAML and never hardcodes a credential."""
from pathlib import Path

import pytest
import yaml

from config import settings

pytestmark = pytest.mark.unit

FLOWS = sorted((Path(__file__).resolve().parents[2] / "mobile" / "flows").rglob("*.yaml"))


@pytest.mark.parametrize("flow", FLOWS, ids=lambda p: p.name)
def test_flow_is_valid_yaml(flow):
    config, commands = yaml.safe_load_all(flow.read_text(encoding="utf-8"))
    assert config["appId"] == "id.edot.ework"
    assert isinstance(commands, list) and commands


@pytest.mark.parametrize("flow", FLOWS, ids=lambda p: p.name)
def test_flow_takes_credentials_from_env(flow):
    # Compared against the values in the local .env, so no credential is ever written in this repo.
    text = flow.read_text(encoding="utf-8")
    for secret in filter(None, (settings.EWORK_COMPANY_ID, settings.EWORK_USERNAME, settings.EWORK_PASSWORD)):
        assert secret not in text, f"a credential from .env is hardcoded in {flow.name}"
