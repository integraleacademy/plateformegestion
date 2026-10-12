from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

import app
from services.dotation_contracts import DEFAULTS, SIGNATURE_FIELDS, generate_pdf, read_contract_form
from yousign_service import YousignError


def values():
    return {**DEFAULTS, "nom": "DUPONT", "prenom": "Élodie", "email": "elodie@example.test",
            "adresse": "12 avenue des Écoles, 83480 Puget-sur-Argens", "telephone": "0612345678",
            "ipad": "SERIAL-TEST-123", "badge": "BADGE-456", "date_remise": "2026-10-12", "date_fin": "2028-06-30"}


@pytest.fixture
def workflow(monkeypatch, tmp_path):
    store = {"data": [{"id": "dot-test", "statut": "Dotation à distribuer", "commentaire": "", **values()}]}
    monkeypatch.setattr(app, "load_dotations", lambda: deepcopy(store["data"]))
    monkeypatch.setattr(app, "save_dotations", lambda data: store.update(data=deepcopy(data)))
    manager = app.dotation_workflow
    monkeypatch.setattr(manager, "directory", str(tmp_path / "pdfs"))
    monkeypatch.setattr(manager, "lock_path", str(tmp_path / "dotations.lock"))
    client = app.app.test_client()
    with client.session_transaction() as session:
        session.update(admin_logged=True, admin_session_version=app.ADMIN_SESSION_VERSION, dotation_csrf="test-csrf")
    form = {**values(), "chargeur": "1", "csrf_token": "test-csrf"}
    return client, manager, store, form


def prepare(workflow):
    client, manager, store, form = workflow
    result = client.post("/dotations/dot-test/contrat", data=form)
    assert result.status_code == 302
    contract = store["data"][0]["contract"]
    return {"version": contract["id"], "csrf_token": "test-csrf"}


class FakeYousign:
    def __init__(self):
        self.config = SimpleNamespace(authentication_mode="no_otp")
        self.calls, self.content = [], b""
        self.status, self.signer_statuses = "ongoing", ["notified", "notified"]
        self.fail_activation = False

    def create_signature_request(self, name, external_id):
        self.calls.append(("create", external_id))
        return {"id": "sr-test"}

    def upload_file(self, srid, content, filename, parse_anchors):
        self.content = content
        assert parse_anchors is False
        self.calls.append(("upload", srid))
        return {"id": "doc-test"}

    def add_signer(self, srid, first, last, email, **kwargs):
        self.calls.append(("signer", email, kwargs))
        return {"id": email}

    def add_signature_field(self, srid, docid, signerid, **kwargs):
        self.calls.append(("field", signerid, kwargs))
        return {"id": "field-" + signerid}

    def activate_signature_request(self, srid):
        self.calls.append(("activate", srid))
        if self.fail_activation:
            raise YousignError("Réponse perdue après activation")
        return {"status": "ongoing"}

    def get_signature_request(self, srid):
        return {"id": srid, "status": self.status}

    def get_signature_request_signers(self, srid):
        return [{"status": status} for status in self.signer_statuses]

    def download_signed_documents(self, srid):
        return self.content

    def request(self, method, path):
        self.calls.append((method, path))
        return {}

    def cancel_signature_request(self, srid, note):
        self.calls.append(("cancel", srid))
        return {}


def test_pdf_content_inventory_amounts_and_blank_signature_areas(tmp_path):
    path = tmp_path / "convention.pdf"
    generate_pdf(values(), str(path), app.dotation_workflow.logo, "2026-10-12")
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) == 3
    assert all(value in text for value in ("Élodie DUPONT", "12 avenue des Écoles", "SERIAL-TEST-123", "BADGE-456", "30 juin 2028"))
    assert all(f"Article {i}" in text for i in range(1, 6))
    assert "400,00 euros" in text and "20,00 euros" in text
    assert "64GB" not in text and "MINTSA" not in text and "sc_sign1" not in text
    assert len(reader.pages[2].images) == 1  # logo only: no pasted signature
    for field in SIGNATURE_FIELDS.values():
        assert field["x"] + field["width"] < float(reader.pages[2].mediabox.width)
        assert field["y"] + field["height"] < float(reader.pages[2].mediabox.height)


def test_generate_and_preview_works_for_existing_legacy_dotation(workflow):
    client, _, store, _ = workflow
    del store["data"][0]["adresse"]
    assert client.get("/dotations/dot-test/contrat").status_code == 200
    post = prepare(workflow)
    pdf = client.get("/dotations/dot-test/contrat/pdf?version=" + post["version"])
    assert pdf.mimetype == "application/pdf" and len(PdfReader(BytesIO(pdf.data)).pages) == 3
    html = client.get("/dotations/dot-test/contrat").get_data(as_text=True)
    assert "Envoyer en signature Yousign" in html and "Générer une nouvelle version" in html


@pytest.mark.parametrize("field,value", [("adresse", ""), ("date_fin", "2025-01-01"), ("email", "invalid"),
                                          ("penalite_ipad", "NaN"), ("penalite_badge", "-1"), ("penalite_chargeur", "1.234")])
def test_validation_does_not_change_data_or_generate_contract(workflow, field, value):
    client, _, store, form = workflow
    before = deepcopy(store["data"])
    response = client.post("/dotations/dot-test/contrat", data={**form, field: value})
    assert response.status_code == 200
    assert store["data"] == before


def test_two_signatures_no_duplicates_and_signed_download(workflow, monkeypatch):
    client, manager, store, _ = workflow
    post = prepare(workflow)
    api = FakeYousign()
    monkeypatch.setattr(manager, "client", lambda: api)
    assert client.post("/dotations/dot-test/contrat/send", data=post).status_code == 302
    assert [c[1] for c in api.calls if c[0] == "signer"] == ["elodie@example.test", "clement@integraleacademy.com"]
    assert [c[2] for c in api.calls if c[0] == "field"] == list(SIGNATURE_FIELDS.values())
    count = len(api.calls)
    client.post("/dotations/dot-test/contrat/send", data=post)
    assert len(api.calls) == count
    api.signer_statuses = ["signed", "notified"]
    response = client.post("/dotations/dot-test/contrat/sync", data=post, headers={"Accept": "application/json"})
    assert response.json["status"] == "partially_signed"
    assert client.post("/dotations/dot-test/contrat/signed", data=post).status_code == 302
    api.status = "done"
    response = client.post("/dotations/dot-test/contrat/signed", data=post)
    assert response.mimetype == "application/pdf"
    assert response.data == api.content
    assert store["data"][0]["contract"]["signedFilename"]


def test_error_after_activation_keeps_request_id_and_cannot_resend(workflow, monkeypatch):
    client, manager, store, _ = workflow
    post = prepare(workflow)
    api = FakeYousign()
    api.fail_activation = True
    monkeypatch.setattr(manager, "client", lambda: api)
    client.post("/dotations/dot-test/contrat/send", data=post)
    state = store["data"][0]["contract"]["yousign"]
    assert state["signatureRequestId"] == "sr-test" and state["status"] == "error"
    client.post("/dotations/dot-test/contrat/send", data=post)
    assert len([c for c in api.calls if c[0] == "create"]) == 1
    client.post("/dotations/dot-test/contrat/sync", data=post)
    assert store["data"][0]["contract"]["yousign"]["status"] == "ongoing"


def test_stale_pdf_and_changed_version_cannot_be_sent(workflow, monkeypatch):
    client, manager, store, _ = workflow
    post = prepare(workflow)
    api = FakeYousign()
    monkeypatch.setattr(manager, "client", lambda: api)
    store["data"][0]["ipad"] = "CHANGED"
    client.post("/dotations/dot-test/contrat/send", data=post)
    assert api.calls == []
    prepare(workflow)
    assert client.post("/dotations/dot-test/contrat/send", data=post).status_code == 409


def test_archive_and_delete_protection(workflow, monkeypatch):
    client, manager, store, form = workflow
    post = prepare(workflow)
    api = FakeYousign()
    monkeypatch.setattr(manager, "client", lambda: api)
    client.post("/dotations/dot-test/contrat/send", data=post)
    client.post("/dotations/dot-test/contrat", data=form)
    assert store["data"][0]["contract"]["id"] == post["version"]
    client.post("/dotations/dot-test/delete", data=post)
    assert len(store["data"]) == 1
    api.status = "done"
    client.post("/dotations/dot-test/contrat/sync", data=post)
    prepare(workflow)
    assert store["data"][0]["contract_history"][0]["id"] == post["version"]
    assert client.post("/dotations/dot-test/contrat/signed", data=post).mimetype == "application/pdf"


def test_webhook_uses_request_status_not_single_signer_event(workflow, monkeypatch):
    client, manager, store, _ = workflow
    post = prepare(workflow)
    api = FakeYousign()
    monkeypatch.setattr(manager, "client", lambda: api)
    monkeypatch.delenv("YOUSIGN_WEBHOOK_SECRET", raising=False)
    client.post("/dotations/dot-test/contrat/send", data=post)
    api.signer_statuses = ["signed", "notified"]
    event = {"event_name": "signer.done", "data": {"signature_request": {"id": "sr-test", "status": "done"}}}
    assert client.post("/webhooks/yousign", json=event).json["target"] == "dotation"
    assert store["data"][0]["contract"]["yousign"]["status"] == "partially_signed"


def test_auth_csrf_and_creation_redirect(workflow):
    client, _, store, form = workflow
    assert app.app.test_client().get("/dotations/dot-test/contrat").status_code == 302
    assert client.post("/dotations/dot-test/contrat", data={}).status_code == 400
    result = client.post("/dotations/add", data=form)
    assert result.status_code == 302 and result.location.endswith("/contrat")
    assert client.get("/dotations").status_code == 200


def test_no_material_and_optional_inventory_items():
    form = {**values(), "ipad": "", "badge": "", "chargeur": ""}
    with pytest.raises(ValueError, match="au moins un matériel"):
        read_contract_form(form)


def test_unknown_create_result_never_creates_a_duplicate(workflow, monkeypatch):
    client, manager, store, _ = workflow
    post = prepare(workflow)
    calls = []
    api = FakeYousign()
    def uncertain(*args):
        calls.append(args)
        raise YousignError("Connexion interrompue")
    api.create_signature_request = uncertain
    monkeypatch.setattr(manager, "client", lambda: api)
    client.post("/dotations/dot-test/contrat/send", data=post)
    client.post("/dotations/dot-test/contrat/send", data=post)
    assert len(calls) == 1
    assert store["data"][0]["contract"]["yousign"]["creationUncertain"] is True


def test_simultaneous_update_does_not_overwrite_send_transaction(workflow):
    client, manager, store, form = workflow
    before = deepcopy(store["data"])
    with manager.transaction():
        response = client.post("/dotations/dot-test/update_date", data={**form, "date_remise": "2027-01-01"})
    assert response.status_code == 302
    assert store["data"] == before


def test_cancel_incomplete_draft_allows_new_version(workflow, monkeypatch):
    client, manager, store, form = workflow
    post = prepare(workflow)
    api = FakeYousign()
    api.fail_activation, api.status = True, "draft"
    monkeypatch.setattr(manager, "client", lambda: api)
    client.post("/dotations/dot-test/contrat/send", data=post)
    client.post("/dotations/dot-test/contrat/cancel", data=post)
    assert ("DELETE", "signature_requests/sr-test") in api.calls
    assert store["data"][0]["contract"]["yousign"]["status"] == "canceled"
    prepare(workflow)
    assert store["data"][0]["contract"]["id"] != post["version"]
