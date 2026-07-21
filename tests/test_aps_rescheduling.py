from copy import deepcopy
from pathlib import Path

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


def test_elearning_curriculum_keeps_remaining_courses_separate_from_presentiel():
    elearning = next(item for item in app.aps_expected_content("elearning_presentiel") if item["modality"] == "elearning")
    presentiel = next(item for item in app.aps_expected_content("elearning_presentiel") if item["modality"] == "presentiel")
    plan = [{"date": "2026-09-01", "slots": [{
        "start": "08:30", "end": "12:00", "duration": 3.5, "durationMinutes": 210,
        "uv": elearning["uv"], "title": elearning["title"], "part": elearning["part"],
        "modality": "elearning", "pedagogicalKey": elearning["key"],
    }]}]

    errors, _, curriculum = app.validate_aps_rescheduling_data(plan, "elearning_presentiel")
    assert errors == []
    assert next(row for row in curriculum["contents"] if row["key"] == elearning["key"])["remainingMinutes"] == elearning["expectedMinutes"] - 210
    assert next(row for row in curriculum["contents"] if row["key"] == presentiel["key"])["remainingMinutes"] == presentiel["expectedMinutes"]


def test_editor_allows_selecting_slot_modality_and_filters_courses_by_it():
    editor = Path("templates/aps_planning_editor.html").read_text(encoding="utf-8")
    assert 'onchange="setEmptySlotModality' in editor
    assert 'value="elearning"' in editor
    assert "x.modality===s.modality" in editor


def test_editor_prioritizes_remaining_aps_hours_and_incomplete_contents():
    editor = Path("templates/aps_planning_editor.html").read_text(encoding="utf-8")
    assert 'id="planningAlert"' in editor
    assert "Planning incomplet" in editor
    assert "Voir les contenus à insérer" in editor
    assert "incompleteOnly=true" in editor
    assert "remaining-badge" in editor
    assert "metric-remaining" in editor


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
