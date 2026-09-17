import copy
from datetime import timedelta
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as application


def make_formateur(status="conforme"):
    return {
        "id": "trainer-1",
        "nom": "Formateur",
        "prenom": "Test",
        "email": "test@example.com",
        "telephone": "",
        "profils": ["APS"],
        "cle": {"attribuee": False, "numero": "", "statut": "non_attribuee"},
        "badge": {"attribue": False, "numero": "", "statut": "non_attribue"},
        "documents": [
            {
                "id": "doc-1",
                "label": "Pièce d’identité",
                "expiration": "",
                "status": status,
                "commentaire": "",
                "attachments": [],
            }
        ],
    }


def login(client):
    with client.session_transaction() as session:
        session["admin_logged"] = True
        session["admin_session_version"] = application.ADMIN_SESSION_VERSION


@pytest.mark.parametrize("route", ["/formateurs/trainer-1", "/formateurs"])
@pytest.mark.parametrize(
    ("manual_status", "required_labels"),
    [
        ("non_concerne", ["Pièce d’identité"]),
        ("a_controler", []),
        ("conforme", []),
        ("non_conforme", []),
    ],
)
def test_read_only_formateur_pages_preserve_manual_document_status(
    monkeypatch, route, manual_status, required_labels
):
    formateurs = [make_formateur(manual_status)]
    monkeypatch.setattr(application, "load_formateurs", lambda: formateurs)
    monkeypatch.setattr(
        application,
        "load_formateur_profils_docs_config",
        lambda: {"APS": required_labels},
    )
    monkeypatch.setattr(application, "render_template", lambda *args, **kwargs: "ok")

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    with application.app.test_client() as client:
        login(client)
        response = client.get(route)

    assert response.status_code == 200
    assert formateurs[0]["documents"][0]["status"] == manual_status


@pytest.mark.parametrize(
    "status", ["non_concerne", "a_controler", "conforme", "non_conforme"]
)
def test_document_status_update_is_persisted(monkeypatch, status):
    storage = [make_formateur("conforme")]

    def load_storage():
        return copy.deepcopy(storage)

    def save_storage(data):
        storage[:] = copy.deepcopy(data)

    monkeypatch.setattr(application, "load_formateurs", load_storage)
    monkeypatch.setattr(application, "save_formateurs", save_storage)

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    with application.app.test_client() as client:
        login(client)
        response = client.post(
            "/formateurs/trainer-1/documents/doc-1/update",
            data={
                "expiration": "",
                "status": status,
                "commentaire": "Statut vérifié",
            },
        )

    assert response.status_code == 200
    assert response.get_json()["document"]["status"] == status
    assert storage[0]["documents"][0]["status"] == status
    assert storage[0]["documents"][0]["commentaire"] == "Statut vérifié"


def test_document_status_update_rejects_unknown_status(monkeypatch):
    storage = [make_formateur("conforme")]
    persisted = []
    monkeypatch.setattr(application, "load_formateurs", lambda: storage)
    monkeypatch.setattr(application, "save_formateurs", lambda data: persisted.append(data))

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    with application.app.test_client() as client:
        login(client)
        response = client.post(
            "/formateurs/trainer-1/documents/doc-1/update",
            data={"status": "statut_inconnu"},
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Statut de document invalide",
    }
    assert storage[0]["documents"][0]["status"] == "conforme"
    assert persisted == []


@pytest.fixture
def compliance_storage(monkeypatch):
    """32 lignes, 24 requises, 23 validations enregistrées dont 4 expirées."""
    trainer = make_formateur()
    yesterday = (application.datetime.now().date() - timedelta(days=1)).isoformat()
    trainer["documents"] = [
        {
            "id": f"doc-{index}",
            "label": f"Critère {index}",
            "status": ("conforme" if index < 23 else
                       "a_controler" if index == 23 else "non_concerne"),
            "expiration": yesterday if index < 4 or index >= 24 else "",
            "commentaire": "",
            "attachments": [],
        }
        for index in range(32)
    ]
    storage = [trainer]
    monkeypatch.setattr(application, "load_formateurs", lambda: copy.deepcopy(storage))
    monkeypatch.setattr(application, "save_formateurs",
                        lambda data: storage.__setitem__(slice(None), copy.deepcopy(data)))
    monkeypatch.setattr(application, "load_formateur_profils_docs_config", lambda: {})
    application.app.config.update(TESTING=True, SECRET_KEY="test")
    return storage


@pytest.mark.parametrize("route", ["/formateurs", "/formateurs/trainer-1",
                                    "/formateurs/trainer-1/print"])
def test_list_detail_and_print_use_same_current_compliance(monkeypatch, compliance_storage, route):
    before = copy.deepcopy(compliance_storage)
    rendered = {}

    def capture_template(template, **context):
        rendered.update(context)
        return "ok"

    monkeypatch.setattr(application, "render_template", capture_template)
    with application.app.test_client() as client:
        login(client)
        response = client.get(route)
    assert response.status_code == 200
    trainer = rendered["formateurs"][0] if route == "/formateurs" else rendered["formateur"]
    assert trainer["conformite"] == {
        "total": 24, "conformes": 19, "a_controler": 1,
        "non_conformes": 4, "non_concernes": 8, "expires": 4, "percent": 79,
    }
    assert sum(d["status"] == "conforme" for d in trainer["documents"]) == 19
    assert trainer["documents"][24]["status"] == "non_concerne"
    assert compliance_storage == before


def test_rendered_counters_exclude_non_applicable_criteria(compliance_storage):
    with application.app.test_client() as client:
        login(client)
        detail = client.get("/formateurs/trainer-1").get_data(as_text=True)
        listing = client.get("/formateurs").get_data(as_text=True)
        printed = client.get("/formateurs/trainer-1/print").get_data(as_text=True)
    assert "19 critères validés sur 24" in detail
    assert ">24 critères requis</button>" in detail
    assert ">19 validés</button>" in detail
    assert ">8 non concernés</button>" in detail
    assert "32 total" not in detail
    assert '<span data-compliance-ratio>19 / 24</span>' in detail
    assert '<strong>19 / 24</strong>' in listing
    assert 'aria-valuemax="24" aria-valuenow="19"' in detail
    assert "19 critères validés sur 24" in printed
    assert "À contrôler" in printed


def test_dashboard_uses_the_same_expiration_rules(compliance_storage):
    with application.app.test_client() as client:
        login(client)
        response = client.get("/formateurs_data.json")
    assert response.get_json()["non_conformes"] == 4
    assert response.get_json()["a_controler"] == 1
    assert application.get_formateurs_global_non_conformites() == 5


@pytest.mark.parametrize("status,expiration,expected_status,expected_total,expected_valid,expected_expired", [
    ("conforme", "2000-01-01", "non_conforme", 24, 19, True),
    ("conforme", "2099-01-01", "conforme", 24, 20, False),
    ("non_concerne", "2000-01-01", "non_concerne", 23, 19, False),
    ("a_controler", "", "a_controler", 24, 19, False),
])
def test_save_returns_current_status_and_counters(
    compliance_storage, status, expiration, expected_status, expected_total,
    expected_valid, expected_expired
):
    with application.app.test_client() as client:
        login(client)
        response = client.post("/formateurs/trainer-1/documents/doc-0/update", data={
            "status": status, "expiration": expiration,
        })
    data = response.get_json()
    assert response.status_code == 200
    assert data["document"]["status"] == expected_status
    assert data["document"]["expired"] is expected_expired
    assert data["conformite"]["total"] == expected_total
    assert data["conformite"]["conformes"] == expected_valid
    assert compliance_storage[0]["documents"][0]["status"] == expected_status
    assert data["conformite"] == application.formateur_document_view(compliance_storage[0])["conformite"]


@pytest.mark.parametrize("expiration", [None, "", "invalid", "today"])
def test_unexpired_documents_remain_valid(expiration):
    trainer = make_formateur()
    trainer["documents"][0]["expiration"] = (
        application.datetime.now().date().isoformat() if expiration == "today" else expiration
    )
    view = application.formateur_document_view(trainer)
    assert view["documents"][0]["status"] == "conforme"
    assert view["conformite"]["conformes"] == 1
    assert view["conformite"]["expires"] == 0


@pytest.mark.parametrize("documents", [[], [dict(status="non_concerne", expiration="2000-01-01")]])
def test_no_required_criteria_has_zero_progress(documents):
    summary = application.formateur_document_view({"documents": documents})["conformite"]
    assert summary["total"] == 0
    assert summary["conformes"] == 0
    assert summary["percent"] == 0
    assert summary["expires"] == 0


def test_manual_reminder_includes_effectively_expired_documents(monkeypatch):
    trainer = make_formateur("conforme")
    trainer["documents"][0]["expiration"] = "2000-01-01"
    storage = [trainer]
    sent = []

    monkeypatch.setattr(application, "load_formateurs", lambda: storage)
    monkeypatch.setattr(application, "save_formateurs", lambda data: None)
    monkeypatch.setattr(
        application,
        "send_email",
        lambda recipient, subject, body: (
            sent.append((recipient, subject, body)) is None,
            None,
        ),
    )

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    with application.app.test_client() as client:
        login(client)
        response = client.post("/formateurs/trainer-1/send_mail")

    assert response.status_code == 302
    assert len(sent) == 1
    assert sent[0][0] == "test@example.com"
    assert "Pièce d’identité" in sent[0][2]
    assert "last_relance" in trainer


def test_failed_manual_reminder_is_not_recorded_as_sent(monkeypatch):
    trainer = make_formateur("non_conforme")
    storage = [trainer]
    saved = []

    monkeypatch.setattr(application, "load_formateurs", lambda: storage)
    monkeypatch.setattr(application, "save_formateurs", lambda data: saved.append(data))
    monkeypatch.setattr(
        application, "send_email", lambda *args, **kwargs: (False, "SMTP indisponible")
    )

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    with application.app.test_client() as client:
        login(client)
        response = client.post("/formateurs/trainer-1/send_mail")
        with client.session_transaction() as session:
            flashes = session.get("_flashes", [])

    assert response.status_code == 302
    assert "last_relance" not in trainer
    assert saved == []
    assert ("error", "Relance non envoyée : SMTP indisponible.") in flashes


def test_email_sender_uses_the_shared_brevo_smtp_configuration(monkeypatch):
    calls = []

    class SMTP:
        def __init__(self, server, port, timeout):
            calls.append(("connect", server, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def starttls(self, context):
            calls.append(("starttls", bool(context)))

        def login(self, login, password):
            calls.append(("login", login, password))

        def sendmail(self, sender, recipients, message):
            calls.append(("sendmail", sender, recipients, message))
            return {}

    monkeypatch.setattr(application.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(application, "BREVO_API_KEY", None)
    monkeypatch.setattr(application, "get_smtp_config", lambda: {
        "server": "smtp-relay.brevo.com",
        "port": 587,
        "login": "brevo-user",
        "password": "test-only",
        "from_email": "contact@example.com",
    })

    success, error = application.send_email(
        "trainer@example.com", "Relance", "<p>Test</p>"
    )

    assert (success, error) == (True, None)
    assert calls[0] == ("connect", "smtp-relay.brevo.com", 587, 30)
    assert calls[2] == ("login", "brevo-user", "test-only")
    assert calls[3][0:3] == (
        "sendmail", "contact@example.com", ["trainer@example.com"]
    )


def test_email_sender_prefers_the_brevo_transactional_api(monkeypatch):
    captured = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b""

    def urlopen(request, data, timeout):
        captured["url"] = request.full_url
        captured["api_key"] = request.get_header("Api-key")
        captured["payload"] = application.json.loads(data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(application, "BREVO_API_KEY", "test-api-key")
    monkeypatch.setattr(application, "BREVO_SENDER_EMAIL", "contact@example.com")
    monkeypatch.setattr(application, "BREVO_FROM_EMAIL", None)
    monkeypatch.setattr(application, "BREVO_SENDER_NAME", "Intégrale Academy")
    monkeypatch.setattr(application.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        application,
        "get_smtp_config",
        lambda: pytest.fail("Le SMTP ne doit pas être utilisé quand l’API Brevo est configurée"),
    )

    success, error = application.send_email(
        "trainer@example.com", "Relance", "<p>Test</p>"
    )

    assert (success, error) == (True, None)
    assert captured == {
        "url": "https://api.brevo.com/v3/smtp/email",
        "api_key": "test-api-key",
        "payload": {
            "sender": {"email": "contact@example.com", "name": "Intégrale Academy"},
            "to": [{"email": "trainer@example.com"}],
            "subject": "Relance",
            "htmlContent": "<p>Test</p>",
        },
        "timeout": 10,
    }
