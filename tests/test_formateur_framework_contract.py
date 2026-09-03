from pathlib import Path

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


def test_yousign_send_creates_only_trainer_signer_with_sms_otp(monkeypatch, tmp_path):
    formateur = complete_formateur()
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
    response = authenticated_client().post("/formateurs/dfff0664/yousign/send")

    assert response.status_code == 302
    assert calls["canceled"]["signature_request_id"] == "sr-legacy-center"
    assert "seul le formateur signe" in calls["canceled"]["custom_note"]
    assert calls["upload"]["pdf_bytes"].startswith(b"%PDF")
    assert calls["upload"]["parse_anchors"] is False
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
