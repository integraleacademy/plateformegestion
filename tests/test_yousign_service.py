import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yousign_service import DEFAULT_YOUSIGN_API_BASE_URL, get_yousign_config, is_yousign_configured


def test_yousign_config_defaults(monkeypatch):
    for key in [
        "YOUSIGN_API_KEY",
        "YOUSIGN_API_BASE_URL",
        "YOUSIGN_BASE_URL",
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


def test_yousign_config_accepts_base_url_alias(monkeypatch):
    monkeypatch.delenv("YOUSIGN_API_BASE_URL", raising=False)
    monkeypatch.setenv("YOUSIGN_BASE_URL", "https://api-sandbox.yousign.app/v3/")

    config = get_yousign_config()

    assert config.base_url == "https://api-sandbox.yousign.app/v3"


def test_aps_trainer_contract_pdf_contains_yousign_anchor_in_trainer_signature(tmp_path):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    import app

    output = tmp_path / "contrat_aps.pdf"
    session_data = {
        "formation": "APS",
        "display_name": "Session APS test",
        "date_debut": "2026-01-05",
        "date_fin": "2026-01-09",
        "date_exam": "2026-01-10",
        "apsPlanningMode": "presentiel",
    }
    contract = {
        "trainerName": "Jean Dupont",
        "trainerEmail": "jean@example.com",
        "trainerPhone": "0600000000",
        "status": "Formateur indépendant",
        "siret": "12345678900010",
        "activityDeclaration": "",
        "address": "1 rue Test",
        "calculatedHours": 7,
        "calculatedDays": 1,
        "billedDays": 1,
        "dailyRate": 300,
        "totalHT": 300,
        "totalTTC": 300,
        "interventions": [{"date": "2026-01-05", "dateLabel": "05/01/2026", "start": "09:00", "end": "17:00", "hours": 7, "module": "UV1", "modality": "Présentiel"}],
    }

    app.generate_aps_trainer_contract_pdf(session_data, contract, str(output))

    text = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(str(output)).pages)
    assert "Signature du formateur" in text
    assert "{{s1|signature|160|60}}" in text
    assert text.count("{{s1|signature|160|60}}") == 1
    assert "s2|signature" not in text


def test_sanitize_yousign_external_id_removes_forbidden_chars():
    from yousign_service import sanitize_yousign_external_id

    value = "session:abc/é#?=({bad})[] aps_contract:21f64b74-fae5-41d1-986e-fcce0e5af9e8"

    assert sanitize_yousign_external_id(value) == "session-abc-bad- aps_contract-21f64b74-fae5-41d1-986e-fcce0e5af9e8"


def test_sanitize_yousign_external_id_fallback_and_length():
    from yousign_service import sanitize_yousign_external_id

    assert sanitize_yousign_external_id("///") == "aps-trainer-contract"
    assert len(sanitize_yousign_external_id("a" * 250)) == 180


def test_create_signature_request_sanitizes_external_id(monkeypatch):
    from yousign_service import YousignClient, YousignConfig

    captured = {}
    client = YousignClient(YousignConfig(api_key="key", base_url="https://example.test"))

    def fake_request(method, path, payload=None, headers=None):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"id": "sr_1"}

    monkeypatch.setattr(client, "request", fake_request)
    client.create_signature_request("Contrat", external_id="session:abc/def")

    assert captured["payload"]["external_id"] == "session-abc-def"


def test_yousign_add_signer_can_use_pdf_text_tags_without_manual_fields(monkeypatch):
    from yousign_service import YousignClient, YousignConfig

    captured = {}
    client = YousignClient(YousignConfig(api_key="key", base_url="https://example.test"))

    def fake_request(method, path, payload=None, headers=None):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"id": "signer_1"}

    monkeypatch.setattr(client, "request", fake_request)
    client.add_signer("sr_1", "Jean", "Dupont", "jean@example.com", document_id="doc_1", use_text_tags=True)

    assert "fields" not in captured["payload"]
