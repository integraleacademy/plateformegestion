import copy
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
