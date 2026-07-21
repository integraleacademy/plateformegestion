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


def test_elearning_slot_can_be_saved_with_an_empty_slot_of_another_modality():
    elearning = next(item for item in app.aps_expected_content("elearning_presentiel") if item["modality"] == "elearning")
    plan = [{"date": "2026-09-01", "slots": [
        {"start": "08:30", "end": "09:30", "duration": 1, "durationMinutes": 60,
         "uv": elearning["uv"], "title": elearning["title"], "part": elearning["part"],
         "modality": "elearning", "pedagogicalKey": elearning["key"]},
        slot("", "", "13:30", "16:30", minutes=180, isEmpty=True),
    ]}]

    errors, _, _ = app.validate_aps_rescheduling_data(plan, "elearning_presentiel")

    assert errors == []


def test_editor_allows_selecting_slot_modality_and_filters_courses_by_it():
    editor = Path("templates/aps_planning_editor.html").read_text(encoding="utf-8")
    assert 'onchange="setEmptySlotModality' in editor
    assert 'value="elearning"' in editor
    assert "x.modality===s.modality" in editor
    assert "slots.splice(si,1,inserted" in editor
    assert "isEmpty:true" in editor
    assert "function insertableMinutes(day,slot)" in editor
    assert "a.planned===0&&available<=0" in editor


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


def test_api_recalculates_persists_times_and_reports_daily_availability(monkeypatch):
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    session = {"id": "aps-times", "formation": "APS", "apsPlanningMode": "full_presentiel", "apsDailyCapacityMinutes": 420,
               "apsPlanningData": [{"date": "2026-09-01", "slots": [slot("UV4", "Stratégique")]}]}
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    changed = deepcopy(session["apsPlanningData"])
    changed[0]["slots"][0].update({"start": "09:00", "end": "11:30", "durationMinutes": 999, "duration": 99})
    with app.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        response = client.put("/api/sessions/aps-times/aps-planning", json={"planningData": changed})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["planningData"][0]["slots"][0]["durationMinutes"] == 150
        assert payload["dayAvailability"] == [{"date": "2026-09-01", "capacityMinutes": 420, "plannedMinutes": 150, "availableMinutes": 270}]
        refreshed = client.get("/api/sessions/aps-times/aps-planning").get_json()
    assert refreshed["apsPlanningData"][0]["slots"][0]["start"] == "09:00"
    assert refreshed["apsPlanningData"][0]["slots"][0]["end"] == "11:30"


def test_insert_four_hours_of_uv1_from_empty_slot_persists_and_leaves_three_hours(monkeypatch):
    """Regression: an empty 08:30-12:30 slot must accept a partial UV1 insertion."""
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    uv1 = next(item for item in app.aps_expected_content() if item["key"] == "UV1")
    session = {
        "id": "aps-insert-four-hours", "formation": "APS", "apsPlanningMode": "full_presentiel",
        # One prior 7-hour insertion means UV1 has exactly seven hours left.
        "apsPlanningData": [
            {"date": "2026-09-01", "slots": [
                slot("UV1", uv1["title"], "08:30", "12:30", 240, pedagogicalKey="UV1"),
                slot("UV1", uv1["title"], "13:30", "16:30", 180, pedagogicalKey="UV1"),
            ]},
            {"date": "2026-09-02", "slots": [slot("", "", "08:30", "12:30", 240, isEmpty=True)]},
        ],
    }
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    inserted_plan = deepcopy(session["apsPlanningData"])
    inserted_plan[1]["slots"][0] = slot("UV1", uv1["title"], "08:30", "12:30", 240, pedagogicalKey="UV1")

    with app.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        response = client.put("/api/sessions/aps-insert-four-hours/aps-planning", json={"planningData": inserted_plan})
        assert response.status_code == 200
        payload = response.get_json()
        saved_slot = payload["planningData"][1]["slots"][0]
        assert saved_slot["uv"] == "UV1"
        assert saved_slot["start"] == "08:30"
        assert saved_slot["end"] == "12:30"
        assert saved_slot["durationMinutes"] == 240
        assert next(item for item in payload["curriculum"]["contents"] if item["key"] == "UV1")["remainingMinutes"] == 180
        refreshed = client.get("/api/sessions/aps-insert-four-hours/aps-planning").get_json()

    assert refreshed["apsPlanningData"][1]["slots"][0]["uv"] == "UV1"
    assert next(item for item in refreshed["curriculum"]["contents"] if item["key"] == "UV1")["remainingMinutes"] == 180


def test_session_f867ab33_inserts_uv1_despite_over_capacity_legacy_day(monkeypatch):
    """A 7-hour overrun on 2026-08-12 cannot block a 2026-07-21 insertion."""
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    uv1 = next(item for item in app.aps_expected_content() if item["key"] == "UV1")
    uv2 = next(item for item in app.aps_expected_content() if item["key"] == "UV2")
    uv3 = next(item for item in app.aps_expected_content() if item["key"] == "UV3")
    session = {
        "id": "f867ab33", "formation": "APS", "apsPlanningMode": "full_presentiel",
        "apsDailyCapacityMinutes": 420,
        "apsPlanningData": [
            # UV1 has seven hours remaining before the requested insertion.
            {"date": "2026-07-20", "slots": [
                slot("UV1", uv1["title"], "08:30", "12:30", 240, pedagogicalKey="UV1"),
                slot("UV1", uv1["title"], "13:30", "16:30", 180, pedagogicalKey="UV1"),
            ]},
            {"date": "2026-07-21", "slots": [
                slot("", "", "08:30", "12:30", 240, isEmpty=True),
                # Old, overlapping placeholders must stay stored but ignored.
                slot("", "", "09:00", "10:00", 60, isEmpty=True),
                slot("", "", "09:30", "11:00", 90, isEmpty=True),
            ]},
            {"date": "2026-08-12", "slots": [
                slot("UV2", uv2["title"], "08:30", "12:30", 240, pedagogicalKey="UV2"),
                slot("UV3", uv3["title"], "13:30", "17:30", 240, pedagogicalKey="UV3"),
            ]},
        ],
    }
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    inserted_plan = deepcopy(session["apsPlanningData"])
    inserted_plan[1]["slots"][0] = slot(
        "UV1", uv1["title"], "08:30", "12:30", 240, pedagogicalKey="UV1"
    )

    with app.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        response = client.put(
            "/api/sessions/f867ab33/aps-planning", json={"planningData": inserted_plan}
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["warnings"] == [{
            "date": "2026-08-12", "plannedMinutes": 480, "capacityMinutes": 420,
            "excessMinutes": 60,
            "message": "La journée 2026-08-12 dépasse la durée indicative de 7h.",
        }]
        assert payload["dayAvailability"][1] == {
            "date": "2026-07-21", "capacityMinutes": 420,
            "plannedMinutes": 240, "availableMinutes": 180,
        }
        assert payload["planningData"][1]["slots"][0]["uv"] == "UV1"
        assert payload["planningData"][1]["slots"][1:][0]["isEmpty"] is True
        assert payload["planningData"][1]["slots"][1:][1]["isEmpty"] is True
        assert next(item for item in payload["curriculum"]["contents"] if item["key"] == "UV1")["remainingMinutes"] == 180
        refreshed = client.get("/api/sessions/f867ab33/aps-planning").get_json()

    assert refreshed["apsPlanningData"][1]["slots"][0]["uv"] == "UV1"
    assert refreshed["dayAvailability"][1]["plannedMinutes"] == 240
    assert refreshed["dayAvailability"][1]["availableMinutes"] == 180


def test_editor_delegates_dynamic_course_insert_clicks_and_includes_request_data():
    editor = Path("templates/aps_planning_editor.html").read_text(encoding="utf-8")
    assert 'type="button" class="course-choice" data-action="insert-course"' in editor
    assert "document.addEventListener('click',async event" in editor
    assert "data-session-id=" in editor
    assert "data-planning-date=" in editor
    assert "data-start-time=" in editor
    assert "data-end-time=" in editor
    assert "data-max-duration=" in editor
    assert "method:'PUT'" in editor
    assert "Insertion…" in editor
    assert "Impossible d’insérer ce cours" in editor
    assert 'id="modalError" class="error"' in editor
    assert "modalErr=document.getElementById('modalError')" in editor
    assert "function showActionError(message)" in editor
    assert "const responseText=await r.text()" in editor
    assert "JSON.parse(responseText)" in editor
    assert "j.planningData||j.apsPlanningData||planning" in editor
    assert "const scheduledSlots=(day.slots||[]).filter(slot=>!slot.isEmpty)" in editor


def test_api_rejects_overlaps_and_lunch_crossing_but_not_daily_capacity(monkeypatch):
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    session = {"id": "aps-guardrails", "formation": "APS", "apsPlanningMode": "full_presentiel",
               "apsPlanningData": [{"date": "2026-09-01", "slots": [slot("UV4", "Stratégique")]}]}
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    overlap = [{"date": "2026-09-01", "slots": [slot("UV4", "A", "08:30", "12:00"), slot("UV5", "B", "11:30", "12:30")]}]
    titles = {item["key"]: item["title"] for item in app.aps_expected_content()}
    capacity = [{"date": "2026-09-01", "slots": [slot("UV4", titles["UV4"], "08:30", "12:00"), slot("UV5", titles["UV5"], "13:30", "17:00"), slot("UV6", titles["UV6"], "17:00", "17:30")]}]
    lunch = [{"date": "2026-09-01", "slots": [slot("UV4", "A", "08:30", "13:30")]}]
    with app.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        assert any("chevauchent" in message for message in client.put("/api/sessions/aps-guardrails/aps-planning", json={"planningData": overlap}).get_json()["errors"])
        capacity_response = client.put("/api/sessions/aps-guardrails/aps-planning", json={"planningData": capacity})
        assert capacity_response.status_code == 200
        assert capacity_response.get_json()["warnings"][0]["excessMinutes"] == 30
        assert any("pause déjeuner" in message for message in client.put("/api/sessions/aps-guardrails/aps-planning", json={"planningData": lunch}).get_json()["errors"])


def test_capacity_warning_is_structured_and_describes_real_slot_times(monkeypatch):
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    session = {"id": "aps-capacity-details", "formation": "APS", "apsPlanningMode": "full_presentiel",
               "apsDailyCapacityMinutes": 420,
               "apsPlanningData": [{"date": "2026-08-12", "slots": [slot("UV1", "Gestion des premiers secours", "08:30", "12:30", 1), slot("UV2", "Cadre juridique", "13:30", "17:30", 1)]}]}
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    with app.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        response = client.put("/api/sessions/aps-capacity-details/aps-planning", json={"planningData": session["apsPlanningData"]})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["capacityViolations"] == [{
        "date": "2026-08-12", "capacityMinutes": 420, "plannedMinutes": 480, "excessMinutes": 60,
        "slots": [{"start": "08:30", "end": "12:30", "durationMinutes": 240}, {"start": "13:30", "end": "17:30", "durationMinutes": 240}],
    }]
    assert payload["warnings"] == [{
        "date": "2026-08-12", "plannedMinutes": 480, "capacityMinutes": 420,
        "excessMinutes": 60,
        "message": "La journée 2026-08-12 dépasse la durée indicative de 7h.",
    }]


def test_editor_shows_loaded_capacity_alert_and_scroll_link():
    editor = Path("templates/aps_planning_editor.html").read_text(encoding="utf-8")
    assert "Le planning contient ${problems.length} journée" in editor
    assert "Voir la journée concernée" in editor
    assert "scrollToDay" in editor
    assert "Dépassement de ${hours(-a.available)}" in editor
    assert "capacityViolations" in editor
    assert "Vous pouvez continuer à modifier et enregistrer le planning" in editor
    assert "plannedMinutes>dailyCapacityMinutes)errors.push" not in editor
