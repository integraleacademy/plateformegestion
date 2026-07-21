from copy import deepcopy

import app


def slot(uv, title, start="08:30", end="12:00", minutes=210, **extra):
    return {"start": start, "end": end, "duration": minutes / 60, "durationMinutes": minutes,
            "uv": uv, "title": title, "modality": "presentiel", "room": "Salle", "trainer": "Formateur", **extra}


def test_deleted_half_day_becomes_available_from_curriculum_and_can_be_reinserted():
    planned = [{"date": "2026-09-01", "slots": [slot("UV4", "Stratégique")]}]
    errors, _, curriculum = app.validate_aps_rescheduling_data(planned)
    assert errors == []
    assert next(row for row in curriculum["contents"] if row["key"] == "UV4")["remainingMinutes"] == 210

    deleted = deepcopy(planned)
    deleted[0]["slots"][0] = slot("", "", isEmpty=True)
    errors, _, curriculum = app.validate_aps_rescheduling_data(deleted)
    assert errors == []
    assert next(row for row in curriculum["contents"] if row["key"] == "UV4")["remainingMinutes"] == 420

    deleted[0]["slots"][0] = slot("UV4", "Stratégique", pedagogicalKey="UV4")
    errors, _, curriculum = app.validate_aps_rescheduling_data(deleted)
    assert errors == []
    assert next(row for row in curriculum["contents"] if row["key"] == "UV4")["remainingMinutes"] == 210


def test_rescheduling_rejects_overplanning_overlaps_and_unknown_content():
    overplanned = [{"date": "2026-09-01", "slots": [slot("UV4", "Stratégique", minutes=420), slot("UV4", "Stratégique", start="13:30", end="17:00", minutes=210)]}]
    errors, _, _ = app.validate_aps_rescheduling_data(overplanned)
    assert any("dépasse le volume" in error for error in errors)

    overlap = [{"date": "2026-09-01", "slots": [slot("UV4", "Stratégique"), slot("UV5", "Prévention des risques incendie", start="10:00", end="13:30")]}]
    errors, _, _ = app.validate_aps_rescheduling_data(overlap)
    assert any("chevauchent" in error for error in errors)

    unknown = [{"date": "2026-09-01", "slots": [slot("UV99", "Inconnu")]}]
    errors, _, _ = app.validate_aps_rescheduling_data(unknown)
    assert any("inconnu" in error for error in errors)


def test_api_persists_incomplete_old_plan_and_returns_remaining_curriculum(monkeypatch):
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    session = {"id": "aps-reschedule", "formation": "APS", "apsPlanningMode": "full_presentiel", "apsPlanningData": [{"date": "2026-09-01", "slots": [slot("UV4", "Stratégique")]}]}
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    with app.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        response = client.put("/api/sessions/aps-reschedule/aps-planning", json={"planningData": [{"date": "2026-09-01", "slots": [slot("", "", isEmpty=True)]}]})
        assert response.status_code == 200
        payload = response.get_json()
        assert next(row for row in payload["curriculum"]["contents"] if row["key"] == "UV4")["remainingMinutes"] == 420
        refreshed = client.get("/api/sessions/aps-reschedule/aps-planning").get_json()
    assert refreshed["apsPlanningData"][0]["slots"][0]["isEmpty"] is True
    assert refreshed["curriculum"]["remainingMinutes"] == refreshed["curriculum"]["expectedMinutes"]
