import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yousign_service import DEFAULT_YOUSIGN_API_BASE_URL, get_yousign_config, is_yousign_configured


def test_yousign_config_defaults(monkeypatch):
    for key in [
        "YOUSIGN_API_KEY",
        "YOUSIGN_API_BASE_URL",
        "YOUSIGN_WEBHOOK_SECRET",
        "YOUSIGN_CONTRACT_TEMPLATE_ID",
        "YOUSIGN_SIGNATURE_LEVEL",
        "YOUSIGN_AUTHENTICATION_MODE",
        "YOUSIGN_DELIVERY_MODE",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = get_yousign_config()

    assert config.api_key == ""
    assert config.base_url == DEFAULT_YOUSIGN_API_BASE_URL
    assert config.signature_level == "electronic_signature"
    assert config.authentication_mode == "no_otp"
    assert config.delivery_mode == "email"
    assert not is_yousign_configured()


def test_yousign_config_env(monkeypatch):
    monkeypatch.setenv("YOUSIGN_API_KEY", " secret ")
    monkeypatch.setenv("YOUSIGN_API_BASE_URL", "https://api-sandbox.yousign.app/v3/")
    monkeypatch.setenv("YOUSIGN_WEBHOOK_SECRET", "hook")
    monkeypatch.setenv("YOUSIGN_SIGNATURE_LEVEL", "electronic_signature")
    monkeypatch.setenv("YOUSIGN_AUTHENTICATION_MODE", "email_otp")
    monkeypatch.setenv("YOUSIGN_DELIVERY_MODE", "email")

    config = get_yousign_config()

    assert config.api_key == "secret"
    assert config.base_url == "https://api-sandbox.yousign.app/v3"
    assert config.webhook_secret == "hook"
    assert config.authentication_mode == "email_otp"
    assert is_yousign_configured()
