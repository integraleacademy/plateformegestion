import app


def authenticated_client():
    client = app.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["admin_logged"] = True
        flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
    return client


def a3p_session():
    return {
        "id": "a3p-session",
        "formation": "A3P",
        "date_debut": "2026-09-01",
        "date_fin": "2026-09-01",
        "date_exam": "2026-09-02",
        "a3pTrainerName": "Véronique LISCIA",
        "a3pPlanningData": [
            {
                "date": "2026-09-01",
                "slots": [
                    {
                        "start": "08:30",
                        "end": "12:30",
                        "durationMinutes": 240,
                        "code": "UV1",
                        "title": "SST",
                        "trainer": "Véronique LISCIA",
                        "room": "Salle 1",
                    }
                ],
            }
        ],
        "a3pPlanningBuilder": {
            "scheduleConfig": {
                "trainerEmail": "veronique@example.com",
                "trainerPhone": "0612345678",
                "trainerAddress": "1 rue du Test",
                "trainerCompany": "123 456 789 00010",
                "dailyRate": "340",
            }
        },
    }


def test_a3p_contract_preview_reuses_complete_trainer_contract_flow(monkeypatch):
    session = a3p_session()
    monkeypatch.setattr(app, "load_sessions", lambda: {"sessions": [session], "jurys": []})
    monkeypatch.setattr(app, "load_formateurs", lambda: [])

    response = authenticated_client().get("/api/sessions/a3p-session/aps-trainer-contracts/preview")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["trainers"][0]["name"] == "Véronique LISCIA"
    assert payload["trainers"][0]["totalHours"] == 4
    assert payload["trainers"][0]["defaults"] == {
        "email": "veronique@example.com",
        "phone": "0612345678",
        "address": "1 rue du Test",
        "siret": "123 456 789 00010",
        "dailyRate": "340",
    }


def test_legacy_a3p_contract_is_migrated_once_with_yousign_fields(monkeypatch):
    session = a3p_session()
    session["a3pTrainerContract"] = {
        "id": "legacy-contract",
        "pdfFilename": "contrat_formateur_a3p_legacy.pdf",
        "generatedAt": "2026-08-25 15:46:00",
        "dailyRate": 340,
        "vatEnabled": False,
    }
    monkeypatch.setattr(app, "load_formateurs", lambda: [])

    with app.app.test_request_context("/sessions/a3p-session"):
        assert app.migrate_legacy_a3p_trainer_contract(session) is True
        assert app.migrate_legacy_a3p_trainer_contract(session) is False

    contracts = session["a3pTrainerContracts"]
    assert len(contracts) == 1
    contract = contracts[0]
    assert contract["id"] == "legacy-contract"
    assert contract["trainerName"] == "Véronique LISCIA"
    assert contract["planningName"] == "Véronique LISCIA"
    assert contract["trainerEmail"] == "veronique@example.com"
    assert contract["trainerPhone"] == "0612345678"
    assert contract["billedDays"] == 1
    assert contract["totalHT"] == 340
    assert contract["yousign"]["status"] == "draft"
    assert contract["pdfUrl"].endswith("/sessions/a3p-session/aps-trainer-contracts/legacy-contract/view")


def test_a3p_contract_generation_uses_a3p_storage_and_preserves_planning_name(monkeypatch):
    session = a3p_session()
    sessions_data = {"sessions": [session], "jurys": []}
    saved = {}
    generated = {}
    monkeypatch.setattr(app, "load_sessions", lambda: sessions_data)
    monkeypatch.setattr(app, "save_sessions", lambda data: saved.setdefault("data", data))
    monkeypatch.setattr(app, "load_formateurs", lambda: [])
    monkeypatch.setattr(
        app,
        "generate_session_trainer_contract_pdf",
        lambda session_data, contract, output_path: generated.update({"contract": contract, "path": output_path}),
    )

    response = authenticated_client().post(
        "/api/sessions/a3p-session/aps-trainer-contracts/generate",
        json={
            "trainers": [
                {
                    "name": "Véronique LISCIA",
                    "planningName": "Véronique LISCIA",
                    "email": "veronique@example.com",
                    "phone": "0612345678",
                    "dailyRate": 340,
                    "billedDays": 1,
                    "vatEnabled": False,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert "apsTrainerContracts" not in session
    assert len(session["a3pTrainerContracts"]) == 1
    contract = session["a3pTrainerContracts"][0]
    assert contract["planningName"] == "Véronique LISCIA"
    assert contract["totalHT"] == 340
    assert contract["yousign"]["status"] == "draft"
    assert session["a3pTrainerContract"]["id"] == contract["id"]
    assert generated["path"].endswith(f"contrat_formateur_a3p_a3p-session_{contract['id']}.pdf")
    assert saved["data"] is sessions_data


def test_regenerating_a3p_documents_does_not_overwrite_existing_contract(monkeypatch):
    session = a3p_session()
    existing_contract = {
        "id": "signed-contract",
        "trainerName": "Véronique LISCIA",
        "yousign": {"status": "signed", "signatureRequestId": "sr-signed"},
    }
    existing_document = {"path": "/tmp/signed-contract.pdf", "generated_at": "2026-08-25 15:46:00"}
    session.update(
        {
            "a3pTrainerModulesStatus": "validated",
            "a3pTrainerContract": existing_contract,
            "a3pTrainerContracts": [existing_contract],
            "a3p_documents": {"contract": existing_document},
        }
    )
    sessions_data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: sessions_data)
    monkeypatch.setattr(app, "save_sessions", lambda data: None)
    monkeypatch.setattr(app, "can_generate_a3p_documents_state", lambda state: True)
    monkeypatch.setattr(app, "mark_a3p_manual_modules_admin_validated", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "validate_a3p_planning", lambda planning, exam_date: ([], {"totalHours": 328}))
    monkeypatch.setattr(app, "generate_a3p_planning_pdf", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "generate_a3p_attendance_pdf", lambda *args, **kwargs: None)

    response = authenticated_client().post(
        "/api/sessions/a3p-session/a3p-documents/generate",
        json={
            "scheduleConfig": {
                "trainerFirstName": "Véronique",
                "trainerLastName": "LISCIA",
                "startDate": "2026-09-01",
                "endDate": "2026-09-01",
                "examDate": "2026-09-02",
                "room": "Salle 1",
                "lockedModules": {},
            },
            "planning": session["a3pPlanningData"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert session["a3pTrainerContract"] is existing_contract
    assert session["a3pTrainerContracts"] == [existing_contract]
    assert session["a3p_documents"]["contract"] is existing_document


def test_yousign_webhook_updates_a3p_contract(monkeypatch):
    session = a3p_session()
    session["a3pTrainerContracts"] = [
        {
            "id": "contract-a3p",
            "yousign": {
                "signatureRequestId": "sr-a3p",
                "externalId": "a3p-trainer-contract-contract-a3p",
                "status": "ongoing",
            },
        }
    ]
    sessions_data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_formateurs", lambda: [])
    monkeypatch.setattr(app, "load_sessions", lambda: sessions_data)
    monkeypatch.setattr(app, "save_sessions", lambda data: None)
    monkeypatch.setattr(
        app,
        "sync_yousign_signature_request_from_api",
        lambda signature_request_id, now=None: {
            "status": "signed",
            "apiStatus": "done",
            "apiSignerStatus": "signed",
            "apiHttpStatus": "200",
            "lastSyncedAt": now,
            "signedAt": now,
        },
    )
    monkeypatch.setenv("YOUSIGN_WEBHOOK_SECRET", "")

    response = app.app.test_client().post(
        "/webhooks/yousign",
        json={
            "event_name": "signature_request.done",
            "data": {
                "signature_request": {
                    "id": "sr-a3p",
                    "external_id": "a3p-trainer-contract-contract-a3p",
                }
            },
        },
    )

    assert response.status_code == 200
    assert response.get_json()["target"] == "a3p_trainer_contract"
    assert session["a3pTrainerContracts"][0]["yousign"]["status"] == "signed"
