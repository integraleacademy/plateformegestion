from pathlib import Path
from copy import deepcopy
from datetime import datetime
from io import BytesIO
import re

import pytest
from pypdf import PdfReader

import app


def authenticated_client():
    client = app.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["admin_logged"] = True
        flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
    return client


def complete_formateur():
    return {
        "id": "dfff0664",
        "prenom": "Élodie",
        "nom": "Dupont-Martin",
        "email": "elodie@example.com",
        "telephone": "06 12 34 56 78",
        "date_naissance": "1990-05-17",
        "adresse_postale": "12 avenue des Formateurs, 83480 Puget-sur-Argens",
        "nda": "93830000083",
        "siret": "12345678900012",
        "documents": [],
        "profils": ["PRESTATAIRE"],
    }


def test_framework_contract_pdf_uses_formateur_data_and_embeds_center_signature(tmp_path):
    output = tmp_path / "contrat-cadre.pdf"

    app.generate_formateur_framework_contract_pdf(
        complete_formateur(),
        str(output),
        "2026-09-03",
    )

    reader = PdfReader(str(output))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) == 15
    assert "Élodie DUPONT-MARTIN" in text
    assert "12 avenue des Formateurs" in text
    assert "17/05/1990" in text
    assert "123 456 789 00012" in text
    assert "jeudi 3 septembre 2026" in text
    assert "Signature et tampon du centre / signature électronique du formateur" in text
    assert len(list(reader.pages[-1].images)) >= 3
    assert "LIBAULT" not in text
    assert "Yannice" not in text
    assert "Oodrive" not in text
    assert "27 janvier 2026" not in text


def test_identity_update_persists_birth_date(monkeypatch):
    formateur = complete_formateur()
    saved = {}
    monkeypatch.setattr(app, "load_formateurs", lambda: [formateur])
    monkeypatch.setattr(app, "save_formateurs", lambda data: saved.setdefault("data", data))

    response = authenticated_client().post(
        "/formateurs/dfff0664/identity/update",
        data={
            "nub": "1234567",
            "date_naissance": "1988-04-02",
            "siret": "12345678900012",
            "adresse_postale": "1 rue du Test",
            "nda": "93830000083",
            "tarif_journalier_ht": "350",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["date_naissance"] == "1988-04-02"
    assert payload["framework_contract_missing_fields"] == []
    assert payload["framework_contract_stale"] is False
    assert formateur["date_naissance"] == "1988-04-02"
    assert saved["data"] == [formateur]


@pytest.mark.parametrize("liscia", [False, True])
def test_yousign_send_creates_only_trainer_signer_with_sms_otp(monkeypatch, tmp_path, liscia):
    formateur = complete_formateur()
    if liscia:
        formateur.update(prenom="Véronique", nom="LISCIA")
    formateur["yousign"] = app.normalize_yousign_state({
        "signatureRequestId": "sr-legacy-center",
        "signerId": "signer-trainer-old",
        "centerSignerId": "signer-center-old",
        "status": "ongoing",
    })
    saved = {}
    calls = {"signers": [], "fields": []}

    class FakeYousignClient:
        def cancel_signature_request(self, signature_request_id, custom_note=""):
            calls["canceled"] = {
                "signature_request_id": signature_request_id,
                "custom_note": custom_note,
            }
            return {}

        def create_signature_request(self, name, external_id=""):
            calls["request"] = {"name": name, "external_id": external_id}
            return {"id": "sr-framework"}

        def upload_file(self, signature_request_id, pdf_bytes, filename, parse_anchors=True):
            calls["upload"] = {
                "signature_request_id": signature_request_id,
                "filename": filename,
                "parse_anchors": parse_anchors,
                "pdf_bytes": pdf_bytes,
            }
            return {"id": "doc-framework"}

        def add_signer(self, signature_request_id, first_name, last_name, email, **kwargs):
            calls["signers"].append({
                "signature_request_id": signature_request_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                **kwargs,
            })
            return {
                "id": "signer-trainer",
                "signature_link": "https://example.test/sign",
                "signature_authentication_mode": "otp_sms",
            }

        def add_signature_field(self, signature_request_id, document_id, signer_id, **kwargs):
            calls["fields"].append({
                "signature_request_id": signature_request_id,
                "document_id": document_id,
                "signer_id": signer_id,
                **kwargs,
            })
            return {"id": f"field-{signer_id}"}

        def activate_signature_request(self, signature_request_id):
            calls["activated"] = signature_request_id
            return {"status": "ongoing"}

    monkeypatch.setattr(app, "FORMATEUR_FILES_DIR", str(tmp_path / "formateurs"))
    monkeypatch.setattr(app, "load_formateurs", lambda: [formateur])
    monkeypatch.setattr(app, "save_formateurs", lambda data: saved.setdefault("data", data))
    monkeypatch.setattr(app, "is_yousign_configured", lambda: True)
    monkeypatch.setattr(app, "YousignClient", FakeYousignClient)
    response = authenticated_client().post(
        "/formateurs/dfff0664/yousign/send", data={"contract_date": "2024-02-29"}
    )

    assert response.status_code == 302
    assert calls["canceled"]["signature_request_id"] == "sr-legacy-center"
    assert "seul le formateur signe" in calls["canceled"]["custom_note"]
    assert calls["upload"]["pdf_bytes"].startswith(b"%PDF")
    assert calls["upload"]["parse_anchors"] is False
    uploaded = PdfReader(BytesIO(calls["upload"]["pdf_bytes"]))
    uploaded_text = "\n".join(page.extract_text() or "" for page in uploaded.pages)
    assert "jeudi 29 février 2024" in uploaded_text
    assert ("6.2 Le Sous" in uploaded_text) is (not liscia)
    assert ("7.2 Cession" in uploaded_text) is (not liscia)
    assert formateur["frameworkContract"]["contractDate"] == "2024-02-29"
    assert [signer["email"] for signer in calls["signers"]] == ["elodie@example.com"]
    assert calls["signers"][0]["force_sms_otp"] is True
    assert calls["signers"][0]["phone_number"] == "+33612345678"
    assert len(calls["fields"]) == 1
    assert calls["fields"][0] == {
        "signature_request_id": "sr-framework",
        "document_id": "doc-framework",
        "signer_id": "signer-trainer",
        "page": 15,
        **app.YOUSIGN_FRAMEWORK_TRAINER_SIGNATURE_FIELD,
    }
    assert calls["activated"] == "sr-framework"
    assert formateur["frameworkContract"]["pageCount"] == 15
    assert formateur["yousign"]["status"] == "ongoing"
    assert formateur["yousign"]["centerSignerId"] == ""
    assert formateur["yousign"]["centerFieldId"] == ""
    assert formateur["yousign"]["signatureAuthenticationMode"] == "otp_sms"
    assert saved["data"] == [formateur]


def test_formateur_detail_shows_framework_contract_actions(monkeypatch):
    formateur = complete_formateur()
    monkeypatch.setattr(app, "load_formateurs", lambda: [formateur])
    monkeypatch.setattr(app, "get_etat_cles_badges", lambda *_args: ({}, {}))

    response = authenticated_client().get("/formateurs/dfff0664")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Contrat cadre de sous-traitance" in html
    assert "Signature et tampon du centre intégrés au PDF" in html
    assert "signature électronique du formateur avec code SMS" in html
    assert "Générer et envoyer pour signature" in html
    assert 'id="framework-contract-missing-fields"' in html
    assert 'id="framework-contract-generate-button"' in html
    assert 'data-framework-contract-action="generate"' in html
    assert 'data-framework-contract-action="send"' in html
    assert 'name="contract_date" type="date" required' in html
    assert 'id="framework-contract-date-dialog"' in html
    assert "saas-dialogs.js?v=e0c5fd0" in html


def test_formateur_detail_can_replace_active_legacy_center_request(monkeypatch):
    formateur = complete_formateur()
    formateur["yousign"] = app.normalize_yousign_state({
        "signatureRequestId": "sr-legacy-center",
        "centerSignerId": "signer-center-old",
        "status": "ongoing",
    })
    monkeypatch.setattr(app, "load_formateurs", lambda: [formateur])
    monkeypatch.setattr(app, "get_etat_cles_badges", lambda *_args: ({}, {}))

    response = authenticated_client().get("/formateurs/dfff0664")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Remplacer la demande de signature" in html
    assert "L’ancienne demande à deux signataires sera annulée" in html


def test_formateur_detail_can_resend_active_trainer_invitation(monkeypatch):
    formateur = complete_formateur()
    formateur["yousign"] = app.normalize_yousign_state({
        "signatureRequestId": "sr-framework",
        "signerId": "signer-trainer",
        "status": "ongoing",
        "recipientEmail": "elodie@example.com",
    })
    monkeypatch.setattr(app, "load_formateurs", lambda: [formateur])
    monkeypatch.setattr(app, "get_etat_cles_badges", lambda *_args: ({}, {}))

    response = authenticated_client().get("/formateurs/dfff0664")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="framework-contract-reminder-button"' in html
    assert "Renvoyer l’invitation de signature" in html


def test_yousign_reminder_resends_active_trainer_invitation(monkeypatch):
    formateur = complete_formateur()
    formateur["yousign"] = app.normalize_yousign_state({
        "signatureRequestId": "sr-framework",
        "signerId": "signer-trainer",
        "status": "ongoing",
        "recipientEmail": "elodie@example.com",
    })
    saved = {}
    calls = {}

    class FakeYousignClient:
        def send_signer_reminder(self, signature_request_id, signer_id):
            calls.update({
                "signature_request_id": signature_request_id,
                "signer_id": signer_id,
            })
            return {}

    monkeypatch.setattr(app, "load_formateurs", lambda: [formateur])
    monkeypatch.setattr(app, "save_formateurs", lambda data: saved.setdefault("data", data))
    monkeypatch.setattr(app, "is_yousign_configured", lambda: True)
    monkeypatch.setattr(app, "YousignClient", FakeYousignClient)

    response = authenticated_client().post("/formateurs/dfff0664/yousign/remind")

    assert response.status_code == 302
    assert calls == {
        "signature_request_id": "sr-framework",
        "signer_id": "signer-trainer",
    }
    assert formateur["yousign"]["lastReminderAt"]
    assert formateur["yousign"]["lastEvent"] == "signer.reminder.sent"
    assert formateur["yousign"]["status"] == "ongoing"
    assert saved["data"] == [formateur]


def test_center_signer_webhook_keeps_trainer_signer_and_marks_partial(monkeypatch):
    formateur = complete_formateur()
    formateur["yousign"] = app.normalize_yousign_state({
        "signatureRequestId": "sr-framework",
        "externalId": "framework-dfff0664",
        "signerId": "signer-trainer",
        "centerSignerId": "signer-center",
        "status": "ongoing",
    })
    monkeypatch.setattr(app, "load_formateurs", lambda: [formateur])
    monkeypatch.setattr(app, "save_formateurs", lambda data: None)
    monkeypatch.setattr(
        app,
        "sync_yousign_signature_request_from_api",
        lambda *_args, **_kwargs: {
            "status": "signed",
            "apiStatus": "ongoing",
            "apiSignerStatus": "signed,not_signed",
            "lastSyncedAt": "2026-09-03T10:00:00",
        },
    )
    monkeypatch.setenv("YOUSIGN_WEBHOOK_SECRET", "")

    response = app.app.test_client().post(
        "/webhooks/yousign",
        json={
            "event_name": "signer.done",
            "data": {
                "signature_request": {
                    "id": "sr-framework",
                    "external_id": "framework-dfff0664",
                },
                "signer": {"id": "signer-center", "status": "signed"},
            },
        },
    )

    assert response.status_code == 200
    assert response.get_json()["target"] == "formateur"
    assert formateur["yousign"]["status"] == "partially_signed"
    assert formateur["yousign"]["signerId"] == "signer-trainer"
    assert formateur["yousign"]["centerSignerId"] == "signer-center"


def test_framework_contract_requires_address_and_valid_siret():
    formateur = complete_formateur()
    formateur["adresse_postale"] = ""
    formateur["siret"] = "123"

    assert app.formateur_framework_contract_missing_fields(formateur) == [
        "adresse postale",
        "SIRET valide à 14 chiffres",
    ]


@pytest.mark.parametrize("first,last,excluded", [
    ("Véronique", "LISCIA", True),
    ("  Ve\u0301ronique ", " Liscia ", True),
    ("VERONIQUE", "liscia", True),
    ("Élodie", "LISCIA", False),
    ("Véronique", "Dupont", False),
    ("Véronique-Marie", "LISCIA", False),
    ("Véronique", "LISCIA DUPONT", False),
    ("", "LISCIA", False),
])
def test_clause_exception_requires_full_identity(first, last, excluded):
    assert app.formateur_framework_contract_excludes_clauses({"prenom": first, "nom": last}) is excluded


def test_variant_removes_only_requested_clauses_including_continuation():
    standard = PdfReader(app.FORMATEUR_FRAMEWORK_CONTRACT_TEMPLATE)
    variant = PdfReader(app.FORMATEUR_FRAMEWORK_CONTRACT_LISCIA_TEMPLATE)
    assert len(variant.pages) == len(standard.pages) == 15
    for index, (original, changed) in enumerate(zip(standard.pages, variant.pages)):
        before = original.extract_text() or ""
        after = changed.extract_text() or ""
        if index == 6:
            prefix = before[:before.index("6.2 Le Sous")]
            retained = before[before.index("7. Propriété"):before.index("7.2 Cession")]
            assert " ".join(after.split()) == " ".join((prefix + retained).split())
        elif index == 7:
            prefix = before[:before.index("en autant d’exemplaires")]
            retained = before[before.index("8. Intuitu personae"):]
            assert " ".join(after.split()) == " ".join((prefix + retained).split())
        else:
            assert before == after


def test_selected_date_survives_regeneration_and_changed_date_rebuilds_pdf(monkeypatch, tmp_path):
    trainer = complete_formateur()
    monkeypatch.setattr(app, "FORMATEUR_FILES_DIR", str(tmp_path))
    initial = app.create_formateur_framework_contract(
        trainer, generated_at=datetime(2026, 10, 12, 9, 30), contract_date="2022-09-01"
    )
    assert trainer["frameworkContract"]["generatedAt"] == "2026-10-12T09:30:00"
    assert trainer["frameworkContract"]["contractDate"] == "2022-09-01"
    assert app.ensure_formateur_framework_contract_pdf(trainer) == initial
    trainer["adresse_postale"] = "20 rue Nouvelle, 83480 Puget-sur-Argens"
    refreshed = app.ensure_formateur_framework_contract_pdf(trainer)
    assert refreshed != initial
    assert trainer["frameworkContract"]["contractDate"] == "2022-09-01"
    assert "jeudi 1 septembre 2022" in PdfReader(refreshed).pages[-1].extract_text()
    changed = app.ensure_formateur_framework_contract_pdf(trainer, contract_date="2023-10-02")
    assert changed != refreshed
    assert "lundi 2 octobre 2023" in PdfReader(changed).pages[-1].extract_text()
    assert Path(initial).exists() and Path(refreshed).exists()


@pytest.mark.parametrize("route", ["contrat-cadre/generate", "yousign/send"])
@pytest.mark.parametrize("value", [None, "", "2026-02-30", "not-a-date", "2026-1-2", "2026-10-12junk"])
def test_invalid_date_has_no_side_effects(monkeypatch, route, value):
    trainer = complete_formateur()
    trainer["yousign"] = app.normalize_yousign_state({
        "signatureRequestId": "legacy", "centerSignerId": "center", "status": "ongoing"
    })
    before = deepcopy(trainer)
    monkeypatch.setattr(app, "load_formateurs", lambda: [trainer])
    monkeypatch.setattr(app, "save_formateurs", lambda *_: pytest.fail("No write expected"))
    monkeypatch.setattr(app, "YousignClient", lambda: pytest.fail("No Yousign call expected"))
    response = authenticated_client().post(
        f"/formateurs/dfff0664/{route}", data={} if value is None else {"contract_date": value}
    )
    assert response.status_code == 302
    assert trainer == before


def test_generate_route_uses_chosen_date_and_keeps_active_signature(monkeypatch, tmp_path):
    trainer = complete_formateur()
    monkeypatch.setattr(app, "FORMATEUR_FILES_DIR", str(tmp_path))
    monkeypatch.setattr(app, "load_formateurs", lambda: [trainer])
    saves = []
    monkeypatch.setattr(app, "save_formateurs", lambda _: saves.append(True))
    client = authenticated_client()
    response = client.post("/formateurs/dfff0664/contrat-cadre/generate", data={"contract_date": "2020-05-18"})
    assert response.status_code == 302
    assert trainer["frameworkContract"]["contractDate"] == "2020-05-18"
    assert saves == [True]
    trainer["yousign"] = app.normalize_yousign_state({"signatureRequestId": "active", "status": "ongoing"})
    before = deepcopy(trainer)
    client.post("/formateurs/dfff0664/contrat-cadre/generate", data={"contract_date": "2021-01-01"})
    assert trainer == before
    assert saves == [True]


@pytest.mark.parametrize("status", ["draft", "approval", "ongoing", "partially_signed"])
def test_regenerate_button_is_available_during_pending_signature(monkeypatch, status):
    trainer = complete_formateur()
    trainer["frameworkContract"] = {"filename": "old.pdf", "contractDate": "2026-09-03"}
    trainer["yousign"] = app.normalize_yousign_state({"signatureRequestId": "sr-pending", "status": status})
    monkeypatch.setattr(app, "load_formateurs", lambda: [trainer])
    monkeypatch.setattr(app, "get_etat_cles_badges", lambda *_: ({}, {}))
    response = authenticated_client().get("/formateurs/dfff0664")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    button = re.search(r'<button\b[^>]*id="framework-contract-generate-button"[^>]*>', html).group()
    assert "disabled" not in button
    assert 'data-replace-signature-request-id="sr-pending"' in html
    assert "La demande de signature en cours sera annulée" in html
    assert 'id="framework-contract-replace-request"' in html
    assert 'formateur-framework-contract.js?v=20261012-2' in html


def pending_trainer(monkeypatch, tmp_path):
    trainer = complete_formateur()
    trainer.update(prenom="Véronique", nom="LISCIA")
    monkeypatch.setattr(app, "FORMATEUR_FILES_DIR", str(tmp_path))
    app.create_formateur_framework_contract(trainer, contract_date="2026-09-03")
    trainer["yousign"] = app.normalize_yousign_state({
        "signatureRequestId": "sr-pending", "signerId": "signer-trainer", "status": "ongoing"
    })
    monkeypatch.setattr(app, "load_formateurs", lambda: [trainer])
    monkeypatch.setattr(app, "is_yousign_configured", lambda: True)
    return trainer


@pytest.mark.parametrize("remote_status", ["ongoing", "approval", "draft", "expired", "canceled"])
def test_confirmed_regeneration_archives_request_and_prepares_pdf_without_sending(monkeypatch, tmp_path, remote_status):
    trainer = pending_trainer(monkeypatch, tmp_path)
    previous = deepcopy(trainer)
    calls, saves = [], []

    class FakeClient:
        def get_signature_request(self, request_id):
            assert request_id == "sr-pending"
            calls.append("status")
            return {"status": remote_status}

        def cancel_signature_request(self, request_id, note):
            assert request_id == "sr-pending"
            assert len(list(tmp_path.rglob("*.pdf"))) == 2  # The replacement PDF exists first.
            calls.append("cancel")

        def request(self, method, path):
            assert (method, path) == ("DELETE", "signature_requests/sr-pending")
            calls.append("delete")

    monkeypatch.setattr(app, "YousignClient", FakeClient)
    monkeypatch.setattr(app, "save_formateurs", lambda _: saves.append(True))
    response = authenticated_client().post("/formateurs/dfff0664/contrat-cadre/generate", data={
        "contract_date": "2022-09-01", "replace_signature_request_id": "sr-pending"
    })
    assert response.status_code == 302
    expected_action = [] if remote_status in {"expired", "canceled"} else ["delete" if remote_status == "draft" else "cancel"]
    assert calls == ["status", *expected_action]
    assert saves == [True]
    assert not trainer["yousign"]["signatureRequestId"]
    assert trainer["frameworkContract"]["contractDate"] == "2022-09-01"
    assert trainer["frameworkContract"]["filename"] != previous["frameworkContract"]["filename"]
    archived = trainer["frameworkContractHistory"][-1]
    assert archived["contract"] == previous["frameworkContract"]
    assert archived["yousign"]["signatureRequestId"] == "sr-pending"
    assert archived["yousign"]["status"] == ("expired" if remote_status == "expired" else "canceled")
    path = Path(app.formateur_framework_contract_directory(trainer["id"])) / trainer["frameworkContract"]["filename"]
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    assert "jeudi 1 septembre 2022" in text
    assert "6.2 Le Sous" not in text and "7.2 Cession" not in text
    assert len(list(tmp_path.rglob("*.pdf"))) == 2


@pytest.mark.parametrize("failure", ["cancel", "signed", "pdf", "changed_request", "unknown_status"])
def test_regeneration_failure_preserves_previous_contract_and_request(monkeypatch, tmp_path, failure):
    trainer = pending_trainer(monkeypatch, tmp_path)
    previous = deepcopy(trainer)
    calls = []

    class FakeClient:
        def get_signature_request(self, request_id):
            calls.append("status")
            return {"status": "done" if failure == "signed" else "unknown" if failure == "unknown_status" else "ongoing"}

        def cancel_signature_request(self, request_id, note):
            calls.append("cancel")
            raise app.YousignError("Annulation refusée", 409, {"message": "Cannot cancel"})

    def fail_pdf(*_args, **_kwargs):
        raise RuntimeError("PDF indisponible")

    monkeypatch.setattr(app, "YousignClient", FakeClient)
    monkeypatch.setattr(app, "save_formateurs", lambda _: pytest.fail("No state should be saved"))
    if failure == "pdf":
        monkeypatch.setattr(app, "generate_formateur_framework_contract_pdf", fail_pdf)
    response = authenticated_client().post("/formateurs/dfff0664/contrat-cadre/generate", data={
        "contract_date": "2022-09-01",
        "replace_signature_request_id": "different-request" if failure == "changed_request" else "sr-pending",
    })
    assert response.status_code == 302
    assert trainer == previous
    assert calls == ([] if failure == "changed_request" else ["status", "cancel"] if failure == "cancel" else ["status"])
    assert len(list(tmp_path.rglob("*.pdf"))) == 1
