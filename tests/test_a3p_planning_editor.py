from copy import deepcopy
from pathlib import Path
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app
from a3p_program import generateA3pSchedule


def _days(count=48):
    current = dt.date(2026, 1, 5)
    result = []
    while len(result) < count:
        if current.weekday() < 5:
            result.append({"date": current.isoformat(), "dayStart": "08:30", "dayEnd": "16:30"})
        current += dt.timedelta(days=1)
    result[10]["dayEnd"] = "12:30"
    result[-1]["dayStart"] = "10:00"
    result[-1]["dayEnd"] = "14:00"
    return result


def _config():
    days = _days()
    return {
        "trainerFirstName": "Jean",
        "trainerLastName": "Dupont",
        "room": "Salle 1",
        "examDate": "2026-04-30",
        "days": days,
        "lockedModules": {
            "UV1": [days[0]["date"], days[1]["date"]],
            "UV5": [
                {"date": days[2]["date"], "start": "08:30", "end": "12:00", "durationMinutes": 210},
                {"date": days[2]["date"], "start": "13:00", "end": "16:30", "durationMinutes": 210},
                {"date": days[3]["date"], "start": "08:30", "end": "12:00", "durationMinutes": 210},
                {"date": days[3]["date"], "start": "13:00", "end": "15:30", "durationMinutes": 150},
            ],
            "UV6A": [day["date"] for day in days[4:11]],
            "UV9": [days[11]["date"], days[12]["date"]],
        },
    }


def _session(session_id="a3p-edit"):
    config = _config()
    planning = generateA3pSchedule(config)["planning"]
    return {
        "id": session_id,
        "formation": "A3P",
        "date_debut": config["days"][0]["date"],
        "date_fin": config["days"][-1]["date"],
        "date_exam": config["examDate"],
        "a3pPlanningData": planning,
        "a3pPlanningBuilder": {"scheduleConfig": config, "preview": planning},
    }


def _login(client):
    with client.session_transaction() as flask_session:
        flask_session["admin_logged"] = True
        flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION


def test_a3p_editor_page_exposes_day_trainer_controls_and_session_button():
    editor = Path("templates/a3p_planning_editor.html").read_text(encoding="utf-8")
    detail = Path("templates/session_detail.html").read_text(encoding="utf-8")
    assert "Formateur de la journée" in editor
    assert "data-apply-field=\"trainer\"" in editor
    assert "3 modules différents maximum par journée" in editor
    assert "Enregistrer et régénérer le PDF" in editor
    assert "edit_a3p_planning_page" in detail


def test_a3p_editor_api_persists_per_slot_trainer_and_recalculates_duration(monkeypatch):
    session = _session()
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    monkeypatch.setattr(app, "load_formateurs", lambda: [{"prenom": "Alice", "nom": "Martin"}])
    changed = deepcopy(session["a3pPlanningData"])
    target = changed[0]["slots"][0]
    expected_minutes = app._a3p_editor_time_minutes(target["end"]) - app._a3p_editor_time_minutes(target["start"])
    target.update({"trainer": "Alice Martin", "room": "Salle B", "durationMinutes": 9999, "title": "Titre falsifié"})

    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        _login(client)
        page_response = client.get("/sessions/a3p-edit/a3p-planning/edit")
        assert page_response.status_code == 200
        assert "Formateur de la journée" in page_response.get_data(as_text=True)
        get_response = client.get("/api/sessions/a3p-edit/a3p-planning")
        assert get_response.status_code == 200
        assert get_response.get_json()["maxDistinctModulesPerDay"] == 3
        assert "Alice Martin" in get_response.get_json()["trainerOptions"]
        response = client.put("/api/sessions/a3p-edit/a3p-planning", json={"planningData": changed})

    assert response.status_code == 200
    payload = response.get_json()
    saved_slot = payload["planningData"][0]["slots"][0]
    assert saved_slot["trainer"] == "Alice Martin"
    assert saved_slot["room"] == "Salle B"
    assert saved_slot["durationMinutes"] == expected_minutes
    assert saved_slot["title"] != "Titre falsifié"
    assert session["a3pPlanningBuilder"]["preview"] == session["a3pPlanningData"]
    assert session["a3pPlanningNeedsRegeneration"] is True


def test_a3p_editor_api_rejects_four_distinct_modules_on_one_day(monkeypatch):
    session = _session("a3p-four-modules")
    original = deepcopy(session["a3pPlanningData"])
    changed = deepcopy(original)
    changed[0]["slots"] = [
        {"code": code, "start": start, "end": end, "trainer": "Jean Dupont", "room": "Salle 1"}
        for code, start, end in (
            ("UV1", "08:00", "09:00"),
            ("UV2", "09:00", "10:00"),
            ("UV3", "10:00", "11:00"),
            ("UV4", "11:00", "12:00"),
        )
    ]
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)

    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        _login(client)
        response = client.put("/api/sessions/a3p-four-modules/a3p-planning", json={"planningData": changed})

    assert response.status_code == 400
    assert any("4 modules différents" in error for error in response.get_json()["errors"])
    assert session["a3pPlanningData"] == original


def test_a3p_editor_can_regenerate_only_the_planning_pdf(monkeypatch, tmp_path):
    session = _session("a3p-pdf")
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    monkeypatch.setattr(app, "A3P_DOC_DIR", str(tmp_path))
    monkeypatch.setattr(app, "load_formateurs", lambda: [])
    monkeypatch.setattr(app, "generate_a3p_planning_pdf", lambda session_data, output_path: Path(output_path).write_bytes(b"%PDF-test"))

    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        _login(client)
        response = client.put("/api/sessions/a3p-pdf/a3p-planning", json={"planningData": session["a3pPlanningData"], "regeneratePdf": True})

    assert response.status_code == 200
    assert response.get_json()["needsRegeneration"] is False
    assert (tmp_path / "planning_a3p_session_a3p-pdf.pdf").exists()
    assert session["a3p_documents"]["planning"]["path"].endswith("planning_a3p_session_a3p-pdf.pdf")
