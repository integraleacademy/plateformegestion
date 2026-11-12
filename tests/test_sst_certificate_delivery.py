"""Verify recipient wiring, protected previews and the real Flask adapters."""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as application


@pytest.fixture
def setup_reminders(monkeypatch, tmp_path):
    source = {
        "id": "sst-example", "formation": "APS", "display_name": "APS <test> & novembre",
        "salle": "Centre <test>", "steps": [], "archived": False,
        "apsPlanningData": [
            {"date": day, "slots": [{"uv": "UV1", "modality": "presentiel", "room": "Centre <test>"}]}
            for day in ("2026-11-10", "2026-11-12")
        ],
    }
    monkeypatch.setattr(application, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(application, "load_sessions", lambda: {"sessions": [deepcopy(source)]})
    monkeypatch.setenv("SST_CERTIFICATE_REMINDERS_ENABLED", "true")
    monkeypatch.setenv("SST_CERTIFICATE_REMINDER_EMAIL", "elsa@example.com")
    monkeypatch.setenv("SST_CERTIFICATE_REMINDER_PHONE", "+33600000001")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://plateformegestion.onrender.com")
    sent = {"email": [], "sms": []}
    monkeypatch.setattr(application, "send_email", lambda *args: (sent["email"].append(args) is None, None))
    monkeypatch.setattr(application, "send_price_adaptator_sms", lambda *args: (sent["sms"].append(args) is None, None))
    application.app.config.update(TESTING=True, SECRET_KEY="sst-test-only")
    return source, sent


def test_flask_adapters_send_to_exact_configured_recipient_once_per_channel(setup_reminders):
    source, sent = setup_reminders
    before = deepcopy(source)
    result = application.process_sst_certificate_reminders(datetime.fromisoformat("2026-11-13T09:00:00+01:00"))
    assert result["email_sent"] == result["sms_sent"] == 1
    assert sent["email"][0][0] == "elsa@example.com"
    assert sent["sms"][0][0] == "+33600000001"
    subject, html = sent["email"][0][1:]
    assert subject == "Certificats SST à saisir — APS"
    assert "Bonjour Elsa" in html
    assert "APS &lt;test&gt; &amp; novembre" in html
    assert "Centre &lt;test&gt;" in html
    assert 'href="https://plateformegestion.onrender.com/sessions/sst-example"' in html
    assert "10/11/2026 et 12/11/2026" in html
    assert "fin le 12/11/2026" in sent["sms"][0][1]
    assert source == before
    assert not application.process_sst_certificate_reminders(datetime.fromisoformat("2026-11-13T10:00:00+01:00"))["email_sent"]
    assert len(sent["email"]) == len(sent["sms"]) == 1


@pytest.mark.parametrize("recipient", ["", "wrong", "elsa@example.com,second@example.com", "elsa@example.com\nBcc:second@example.com"])
def test_invalid_email_never_sends_or_prevents_sms(setup_reminders, monkeypatch, recipient):
    _, sent = setup_reminders
    monkeypatch.setenv("SST_CERTIFICATE_REMINDER_EMAIL", recipient)
    result = application.process_sst_certificate_reminders(datetime.fromisoformat("2026-11-13T09:00:00+01:00"))
    assert result["failed"] == 1 and result["sms_sent"] == 1
    assert not sent["email"] and len(sent["sms"]) == 1


def test_missing_sms_recipient_does_not_prevent_email(setup_reminders, monkeypatch):
    _, sent = setup_reminders
    monkeypatch.delenv("SST_CERTIFICATE_REMINDER_PHONE")
    result = application.process_sst_certificate_reminders(datetime.fromisoformat("2026-11-13T09:00:00+01:00"))
    assert result["email_sent"] == 1 and result["failed"] == 1
    assert len(sent["email"]) == 1 and not sent["sms"]


def test_disabled_automation_does_not_initialize_or_send(setup_reminders, monkeypatch, tmp_path):
    _, sent = setup_reminders
    monkeypatch.setenv("SST_CERTIFICATE_REMINDERS_ENABLED", "false")
    assert application.process_sst_certificate_reminders() == {"enabled": False}
    assert not list(tmp_path.iterdir())
    assert sent == {"email": [], "sms": []}


def test_previews_and_diagnostics_require_auth_and_cannot_send(setup_reminders, tmp_path):
    _, sent = setup_reminders
    client = application.app.test_client()
    paths = ["/api/sst-certificate-reminders", "/sessions/sst-example/sst-certificates/reminder-preview"]
    for path in paths:
        response = client.get(path)
        assert response.status_code in {302, 401}
    with client.session_transaction() as session:
        session.update(admin_logged=True, admin_session_version=application.ADMIN_SESSION_VERSION)
    diagnostic = client.get(paths[0])
    assert diagnostic.status_code == 200
    data = diagnostic.get_json()
    assert data["time"] == "09:00" and data["timezone"] == "Europe/Paris"
    assert data["reminders"][0]["due_on"] == "2026-11-13"
    assert data["configuration"]["email_recipient_configured"]
    assert "elsa@example.com" not in diagnostic.get_data(as_text=True)
    assert "+33600000001" not in diagnostic.get_data(as_text=True)
    preview = client.get(paths[1])
    assert preview.status_code == 200
    assert "13/11/2026" in preview.get_data(as_text=True)
    assert preview.headers["Cache-Control"] == "no-store"
    assert client.get("/sessions/unknown/sst-certificates/reminder-preview").status_code == 404
    assert sent == {"email": [], "sms": []}
    assert not list(tmp_path.iterdir())


def test_grouped_mail_and_sms_preserve_each_session_link_without_sending(setup_reminders):
    _, sent = setup_reminders
    reminders = application.load_sst_certificate_reminders()
    reminders.append({**reminders[0], "name": "Second groupe", "session_id": "second", "url": "https://plateformegestion.onrender.com/sessions/second"})
    html = application.render_sst_certificate_reminder_email(reminders)
    assert html.count("Ouvrir la session") == 2
    assert "/sessions/second" in html
    sms = application.build_sst_certificate_reminder_sms(reminders)
    assert "2 sessions terminées" in sms
    assert "sessions?statut=toutes" in sms
    assert sent == {"email": [], "sms": []}


def test_recipient_readiness_does_not_disclose_configuration_values(setup_reminders, monkeypatch):
    monkeypatch.setattr(application, "BREVO_API_KEY", "test-only")
    monkeypatch.setattr(application, "BREVO_SMS_SENDER", "Academy")
    monkeypatch.setattr(application, "BREVO_SENDER_EMAIL", "sender@example.com")
    assert application.sst_certificate_delivery_configuration() == {
        "email_recipient_configured": True, "sms_recipient_configured": True,
        "email_transport_configured": True, "sms_transport_configured": True,
    }
