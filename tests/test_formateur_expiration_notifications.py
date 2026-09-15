import copy
import fcntl
import html
import io
import re
import sys
from datetime import datetime, timedelta
from email import message_from_string
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as application
from services import formateur_expiration_notifications as notifications


def document(identifier, expiration, status="conforme"):
    return {"id": identifier, "label": f"Document {identifier}", "expiration": expiration,
            "status": status, "commentaire": "", "attachments": []}


@pytest.fixture
def setup_notifications(monkeypatch, tmp_path):
    today = datetime.now().date()
    storage = [{"id": "alice", "prenom": "Alice", "nom": "TEST", "email": "alice@example.com",
                "documents": [document("old", (today - timedelta(days=10)).isoformat()),
                              document("new", today.isoformat()),
                              document("other", today.isoformat()),
                              document("excluded", today.isoformat(), "non_concerne")]}]
    monkeypatch.setattr(application, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(application, "FORMATEUR_FILES_DIR", str(tmp_path / "files"))
    monkeypatch.setattr(application, "load_formateurs", lambda: copy.deepcopy(storage))
    monkeypatch.setattr(application, "save_formateurs",
                        lambda data: storage.__setitem__(slice(None), copy.deepcopy(data)))
    monkeypatch.setattr(application, "get_smtp_config", lambda: {
        "server": "smtp.example.com", "port": 587, "login": "sender@example.com",
        "password": "test-only", "from_email": "sender@example.com",
    })
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://plateformegestion.onrender.com")
    application.app.config.update(TESTING=True, SECRET_KEY="fixture-only")
    sent = []
    monkeypatch.setattr(application, "send_formateur_expiration_notification",
                        lambda trainer, docs: (sent.append((copy.deepcopy(trainer), copy.deepcopy(docs))) is None, None))

    def advance_day():
        class Tomorrow(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(days=1)
        monkeypatch.setattr(application, "datetime", Tomorrow)

    return storage, sent, advance_day


def test_new_expirations_are_grouped_and_remembered_after_restart(setup_notifications, tmp_path):
    storage, sent, advance_day = setup_notifications
    baseline = application.process_formateur_expiration_notifications()
    assert baseline["initialized"] is True
    assert baseline["baseline"] == 1
    assert not sent
    advance_day()
    result = application.process_formateur_expiration_notifications()
    assert result["sent"] == 1
    assert result["documents"] == 2
    assert sent[0][0]["email"] == "alice@example.com"
    assert [doc["id"] for doc in sent[0][1]] == ["new", "other"]
    assert application.process_formateur_expiration_notifications()["sent"] == 0
    assert len(sent) == 1
    assert notifications.last_notification_at(str(tmp_path), "alice")
    # Aucune réécriture du dossier pendant le traitement automatique.
    assert storage[0]["documents"][1]["status"] == "conforme"
    assert application.formateur_document_view(storage[0])["documents"][1]["status"] == "non_conforme"


def test_another_expiration_date_can_trigger_a_new_notification(setup_notifications):
    storage, sent, advance_day = setup_notifications
    application.process_formateur_expiration_notifications()
    advance_day()
    application.process_formateur_expiration_notifications()
    storage[0]["documents"][1]["expiration"] = "2020-01-01"
    result = application.process_formateur_expiration_notifications()
    assert result["sent"] == 1
    assert result["documents"] == 1
    assert sent[-1][1][0]["id"] == "new"


def test_failed_delivery_is_retried_without_repeating_successes(monkeypatch, setup_notifications):
    storage, sent, advance_day = setup_notifications
    application.process_formateur_expiration_notifications()
    storage.append({"id": "bob", "prenom": "Bob", "email": "bob@example.com",
                    "documents": [document("bob-doc", "2020-01-01")]})
    advance_day()
    calls = []

    def delivery(trainer, docs):
        calls.append(trainer["id"])
        return trainer["id"] == "alice", "temporary_error"

    monkeypatch.setattr(application, "send_formateur_expiration_notification", delivery)
    result = application.process_formateur_expiration_notifications()
    assert result["sent"] == 1 and result["failed"] == 1
    assert calls == ["alice", "bob"]
    calls.clear()
    monkeypatch.setattr(application, "send_formateur_expiration_notification",
                        lambda trainer, docs: (calls.append(trainer["id"]) is None, None))
    assert application.process_formateur_expiration_notifications()["sent"] == 1
    assert calls == ["bob"]


def test_overlapping_workers_cannot_send_twice(setup_notifications, tmp_path):
    _, sent, advance_day = setup_notifications
    application.process_formateur_expiration_notifications()
    advance_day()
    with open(tmp_path / (notifications.DATABASE_NAME + ".lock"), "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert application.process_formateur_expiration_notifications()["busy"] is True
        assert not sent
    assert application.process_formateur_expiration_notifications()["sent"] == 1


@pytest.mark.parametrize("email", ["", "wrong", "alice@example.com,bob@example.com", "a@example.com\nBcc:b@example.com"])
def test_invalid_or_multiple_recipients_are_not_sent(setup_notifications, email):
    storage, sent, advance_day = setup_notifications
    application.process_formateur_expiration_notifications()
    storage[0]["email"] = email
    advance_day()
    assert application.process_formateur_expiration_notifications()["failed"] == 1
    assert not sent


def test_admin_alerts_use_same_expiration_boundary_and_ignore_non_concerned(setup_notifications):
    storage, _, advance_day = setup_notifications
    assert [d["doc"]["id"] for d in application._list_formateur_expired_documents(storage)] == ["old"]
    advance_day()
    assert [d["doc"]["id"] for d in application._list_formateur_expired_documents(storage)] == ["old", "new", "other"]


def test_prior_admin_alert_does_not_suppress_trainer_email(setup_notifications):
    storage, sent, advance_day = setup_notifications
    application.process_formateur_expiration_notifications()
    for doc in storage[0]["documents"]:
        doc["expiration_alert_sent_for"] = doc["expiration"]
    advance_day()
    assert application.process_formateur_expiration_notifications()["sent"] == 1


def test_upload_link_allows_replacement_and_clears_old_expiration(setup_notifications):
    storage, _, _ = setup_notifications
    original_expiration = storage[0]["documents"][0]["expiration"]
    url = "/formateurs/alice/upload?token=" + application.generate_upload_token("alice")
    with application.app.test_client() as client:
        page = client.get(url)
        assert page.status_code == 200
        assert "Document old" in page.get_data(as_text=True)
        assert client.get("/formateurs/alice/upload?token=invalid").status_code == 403
        response = client.post(url, data={"doc_id": "old", "files": (io.BytesIO(b"%PDF-1.4\ntest"), "renewed.pdf")})
        assert response.status_code == 302
        page = client.get(url).get_data(as_text=True)
    replaced = storage[0]["documents"][0]
    assert replaced["status"] == "a_controler"
    assert replaced["expiration"] == ""
    assert replaced["replaced_expiration"] == original_expiration
    assert len(replaced["attachments"]) == 1
    assert not application.auto_update_document_status(dict(replaced))
    assert "en attente de vérification" in page
    assert "désormais complet" not in page


def test_cannot_replace_a_non_concerned_document(setup_notifications):
    storage, _, _ = setup_notifications
    before = copy.deepcopy(storage)
    url = "/formateurs/alice/upload?token=" + application.generate_upload_token("alice")
    with application.app.test_client() as client:
        response = client.post(url, data={"doc_id": "excluded", "files": (io.BytesIO(b"file"), "test.pdf")})
    assert response.status_code == 400
    assert storage == before


def test_scheduler_starts_once_and_is_disabled_outside_render(monkeypatch):
    starts = []
    class FakeThread:
        def __init__(self, **kwargs):
            self.options = kwargs
        def is_alive(self):
            return bool(starts)
        def start(self):
            starts.append(self.options)
    monkeypatch.setattr(application.threading, "Thread", FakeThread)
    monkeypatch.setattr(application, "_formateur_expiration_thread", None)
    monkeypatch.setattr(application, "IS_RENDER", False)
    monkeypatch.delenv("FORMATEUR_EXPIRATION_NOTIFICATIONS_ENABLED", raising=False)
    application.start_formateur_expiration_scheduler()
    assert not starts
    monkeypatch.setattr(application, "IS_RENDER", True)
    application.start_formateur_expiration_scheduler()
    application.start_formateur_expiration_scheduler()
    assert len(starts) == 1
    assert starts[0]["target"] == application.formateur_expiration_scheduler_loop


def test_email_has_correct_recipient_secure_link_and_escaped_content(monkeypatch):
    delivered = []
    class SMTP:
        def __init__(self, host, port, timeout):
            assert timeout == 30
        def starttls(self, **kwargs):
            pass
        def login(self, *args):
            pass
        def sendmail(self, sender, recipients, body):
            delivered.append((recipients, message_from_string(body)))
            return {}
        def quit(self):
            raise OSError("Connection closed after message accepted")
        def close(self):
            pass
    monkeypatch.setattr(application.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(application, "get_smtp_config", lambda: {
        "server": "smtp.example.com", "port": 587, "login": "test", "password": "test-only", "from_email": "sender@example.com",
    })
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://plateformegestion.onrender.com")
    application.app.config.update(TESTING=True, SECRET_KEY="fixture-only")
    doc = document("cv", "2026-09-14")
    doc["label"] = "CV <script>test</script>"
    success, _ = application.send_formateur_expiration_notification(
        {"id": "alice", "prenom": "Alice", "email": "alice@example.com"}, [doc],
    )
    assert success is True
    recipients, message = delivered[0]
    assert recipients == ["alice@example.com"]
    assert message["Cc"] is None and message["Bcc"] is None
    parts = {p.get_content_type(): p.get_payload(decode=True).decode() for p in message.get_payload()}
    assert "en cas de contrôle" in parts["text/html"]
    assert "dès que possible" in parts["text/plain"]
    assert "<script>" not in parts["text/html"]
    assert "&lt;script&gt;" in parts["text/html"]
    link = html.unescape(re.search(r'href="([^"]+/formateurs/alice/upload\?[^"]+)"', parts["text/html"]).group(1))
    parsed = urlsplit(link)
    assert parsed.netloc == "plateformegestion.onrender.com"
    assert "token=" + application.generate_upload_token("alice") in parsed.query


def test_unconfigured_smtp_does_not_claim_success(monkeypatch):
    monkeypatch.setattr(application, "get_smtp_config", lambda: {"login": "", "password": "", "from_email": ""})
    assert application.send_formateur_expiration_notification({}, []) == (False, "smtp_not_configured")
