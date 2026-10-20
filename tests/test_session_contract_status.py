from copy import deepcopy

import pytest

import app


def session(formation="SSIAP", **extra):
    return {
        "id": "contract-status", "formation": formation,
        "date_debut": "2026-10-12", "date_fin": "2026-10-27",
        "date_exam": "2026-10-28", "steps": [], "jurys": [], **extra,
    }


def contract(name, signature_status="ongoing", **extra):
    return {"id": name, "trainerName": name, "yousign": {"status": signature_status}, **extra}


@pytest.mark.parametrize("formation", ["APS", "SSIAP", "DIRIGEANT", "AFC_APS_SSIAP"])
def test_uncontracted_planned_trainer_prevents_all_signed(formation):
    data = session(formation, apsPlanningData=[{"date": "2026-10-12", "slots": [
        {"trainer": "Alice Martin", "modality": "presentiel"},
        {"trainer": "Bruno Durant", "modality": "sst"},
        {"trainer": "Cours autonome", "modality": "elearning"},
        {"trainer": "Jury", "modality": "exam"},
    ]}], apsTrainerContracts=[contract("Alice Martin", "signed")])
    before = deepcopy(data)

    summary = app.session_trainer_contract_summary(data)

    assert (summary["signed"], summary["total"], summary["tone"]) == (1, 2, "pending")
    assert "Bruno Durant : Contrat à générer" in summary["details"]
    assert data == before


def test_legacy_a3p_contract_is_counted_once_and_current_version_wins():
    legacy = {"id": "old", "trainerName": "Alice Martin", "yousign_status": "signed"}
    data = session("A3P", a3pTrainerName="Alice Martin", a3pTrainerContract=legacy)
    assert app.session_trainer_contract_summary(data)["tone"] == "signed"

    data["a3pTrainerContracts"] = [contract("Alice Martin", "draft", id="new")]
    summary = app.session_trainer_contract_summary(data)
    assert (summary["signed"], summary["total"], summary["tone"]) == (0, 1, "pending")
    assert summary["label"] == "Contrat formateur à envoyer"


@pytest.mark.parametrize("state", ["partially_signed", "declined", "expired", "canceled", "error"])
def test_unsigned_status_is_not_overridden_by_old_signature_metadata(state):
    data = session(apsTrainerContracts=[contract("Alice", state,
        status="signed", yousign_signed_at="2026-10-01", yousign_status="signed")])
    summary = app.session_trainer_contract_summary(data)
    assert summary["signed"] == 0
    assert summary["tone"] != "signed"


def test_no_contract_is_not_marked_signed():
    summary = app.session_trainer_contract_summary(session())
    assert (summary["total"], summary["signed"], summary["tone"]) == (0, 0, "missing")
    assert app.session_trainer_contract_summary(session("GENERAL")) is None


def test_cards_reflect_signature_webhook_and_archived_contracts(monkeypatch):
    active = session(apsTrainerContracts=[{
        **contract('Alice <Martin>'),
        "yousign": {"status": "ongoing", "signatureRequestId": "sr-status"},
    }])
    archived = session("A3P", id="archived", archived=True, date_debut="2025-10-01",
        date_fin="2025-10-16", date_exam="2025-10-17",
        a3pTrainerContracts=[contract("Bruno", "done"), contract("Claire", "signed")])
    data = {"sessions": [active, archived], "jurys": []}
    api_calls = []
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda data: None)
    monkeypatch.setattr(app, "load_formateurs", lambda: [])
    monkeypatch.setenv("YOUSIGN_WEBHOOK_SECRET", "")

    def sync_signature(request_id, now=None):
        api_calls.append(request_id)
        return {"status": "signed", "apiStatus": "done", "signedAt": now}

    monkeypatch.setattr(app, "sync_yousign_signature_request_from_api", sync_signature)
    with app.app.test_client() as client:
        with client.session_transaction() as auth:
            auth["admin_logged"] = True
            auth["admin_session_version"] = app.ADMIN_SESSION_VERSION
        response = client.get("/sessions")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Contrat formateur à signer" in html
        assert "Contrats formateurs signés (2/2)" in html
        assert "Alice &lt;Martin&gt;" in html
        assert "Alice <Martin>" not in html
        assert api_calls == []

        response = client.post("/webhooks/yousign", json={
            "event_name": "signature_request.done",
            "data": {"signature_request": {"id": "sr-status"}},
        })
        assert response.status_code == 200
        assert response.get_json()["target"] == "aps_trainer_contract"

        html = client.get("/sessions").get_data(as_text=True)
        assert "Contrat formateur signé" in html
        assert "Contrat formateur à signer" not in html
        assert api_calls == ["sr-status"]
