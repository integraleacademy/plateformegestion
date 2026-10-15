from copy import deepcopy
from pathlib import Path
import datetime as dt
import os
import sys
import pytest

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
    editor = Path("templates/a3p_planning_editor.html").read_text(encoding="utf-8") + Path("static/js/a3p-planning-editor.js").read_text(encoding="utf-8")
    detail = Path("templates/session_detail.html").read_text(encoding="utf-8")
    assert "Formateur de la journée" in editor
    assert "data-apply-field=\"trainer\"" in editor
    assert "＋ Ajouter un formateur" in editor
    assert "id=\"trainerDialog\"" in editor
    assert "name=\"trainerDays\"" in editor
    assert "Affecter au planning" in editor
    assert "data-open-trainer-day" in editor
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
        assert "/static/js/a3p-planning-editor.js" in page_response.get_data(as_text=True)
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


def test_a3p_editor_api_compacts_adjacent_identical_slots_from_existing_planning(monkeypatch):
    session = _session("a3p-adjacent-slots")
    day = next(day for day in session["a3pPlanningData"] if any(slot["durationMinutes"] >= 120 for slot in day["slots"]))
    index = next(index for index, slot in enumerate(day["slots"]) if slot["durationMinutes"] >= 120)
    original = day["slots"][index]
    split_minutes = app._a3p_editor_time_minutes(original["start"]) + 45
    split = f"{split_minutes // 60:02d}:{split_minutes % 60:02d}"
    day["slots"][index:index + 1] = [
        {**original, "end": split, "durationMinutes": 45},
        {**original, "start": split, "durationMinutes": original["durationMinutes"] - 45},
    ]
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "load_formateurs", lambda: [])

    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        _login(client)
        response = client.get("/api/sessions/a3p-adjacent-slots/a3p-planning")

    assert response.status_code == 200
    returned_day = next(item for item in response.get_json()["planningData"] if item["date"] == day["date"])
    merged = next(slot for slot in returned_day["slots"] if slot["start"] == original["start"])
    assert merged["end"] == original["end"]
    assert merged["durationMinutes"] == original["durationMinutes"]


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


def test_a3p_editor_deleted_day_is_saved_as_draft_without_changing_documents(monkeypatch):
    session = _session()
    original = deepcopy(session['a3pPlanningData'])
    original_builder = deepcopy(session['a3pPlanningBuilder'])
    changed = deepcopy(original[1:])
    data = {'sessions': [session], 'jurys': []}
    saved = []
    monkeypatch.setattr(app, 'load_sessions', lambda: data)
    monkeypatch.setattr(app, 'save_sessions', lambda value: saved.append(deepcopy(value)))
    monkeypatch.setattr(app, 'load_formateurs', lambda: [])
    app.app.config.update(TESTING=True, SECRET_KEY='test')
    with app.app.test_client() as client:
        _login(client)
        response = client.put('/api/sessions/a3p-edit/a3p-planning', json={'planningData': changed, 'saveDraft': True})
        assert response.status_code == 200
        assert response.json['isDraft'] is True
        assert response.json['validationErrors']
        assert saved
        assert session['a3pPlanningData'] == original
        assert session['a3pPlanningBuilder'] == original_builder
        reloaded = client.get('/api/sessions/a3p-edit/a3p-planning').json
        assert reloaded['isDraft'] is True
        assert [day['date'] for day in reloaded['planningData']] == [day['date'] for day in changed]
        blocked_pdf = client.put('/api/sessions/a3p-edit/a3p-planning', json={'planningData': changed, 'saveDraft': True, 'regeneratePdf': True})
        assert blocked_pdf.status_code == 400
        assert session['a3pPlanningData'] == original
        assert len(saved) == 1


def test_a3p_editor_keeps_empty_drafts_and_empty_days_on_reload(monkeypatch):
    session = _session()
    original = deepcopy(session['a3pPlanningData'])
    data = {'sessions': [session], 'jurys': []}
    monkeypatch.setattr(app, 'load_sessions', lambda: data)
    monkeypatch.setattr(app, 'save_sessions', lambda value: None)
    monkeypatch.setattr(app, 'load_formateurs', lambda: [])
    app.app.config.update(TESTING=True, SECRET_KEY='test')
    with app.app.test_client() as client:
        _login(client)
        for planning in ([], [{'date': '2026-04-27', 'slots': []}]):
            response = client.put('/api/sessions/a3p-edit/a3p-planning', json={'planningData': planning, 'saveDraft': True})
            assert response.status_code == 200
            assert response.json['isDraft'] is True
            reloaded = client.get('/api/sessions/a3p-edit/a3p-planning').json
            assert reloaded['isDraft'] is True
            assert len(reloaded['planningData']) == len(planning)
            assert all(day['slots'] == [] for day in reloaded['planningData'])
            assert session['a3pPlanningData'] == original


def test_a3p_editor_relocated_day_replaces_draft_and_keeps_hours_and_trainers(monkeypatch):
    session = _session()
    original = deepcopy(session['a3pPlanningData'])
    changed = deepcopy(original)
    removed_day = changed.pop(0)
    removed_day['date'] = '2026-04-27'
    changed.append(removed_day)
    session['a3pPlanningEditorDraft'] = original[1:]
    session['a3pPlanningEditorDraftModifiedAt'] = '2026-01-01 09:00:00'
    data = {'sessions': [session], 'jurys': []}
    monkeypatch.setattr(app, 'load_sessions', lambda: data)
    monkeypatch.setattr(app, 'save_sessions', lambda value: None)
    monkeypatch.setattr(app, 'load_formateurs', lambda: [])
    app.app.config.update(TESTING=True, SECRET_KEY='test')
    with app.app.test_client() as client:
        _login(client)
        response = client.put('/api/sessions/a3p-edit/a3p-planning', json={'planningData': changed, 'saveDraft': True})
        assert response.status_code == 200
        assert response.json['isDraft'] is False
        assert response.json['summary']['totalHours'] == 328
        assert 'a3pPlanningEditorDraft' not in session
        assert 'a3pPlanningEditorDraftModifiedAt' not in session
        new_day = next(day for day in response.json['planningData'] if day['date'] == '2026-04-27')
        assert new_day['slots'] == app.normalize_a3p_editor_planning([removed_day])[0]['slots']
        assert all(day['date'] != original[0]['date'] for day in response.json['planningData'])
        assert session['a3pPlanningBuilder']['preview'] == session['a3pPlanningData']
        assert client.get('/api/sessions/a3p-edit/a3p-planning').json['isDraft'] is False


def test_a3p_editor_draft_rejects_unusable_dates_duplicates_and_times(monkeypatch):
    session = _session()
    original = deepcopy(session['a3pPlanningData'])
    data = {'sessions': [session], 'jurys': []}
    monkeypatch.setattr(app, 'load_sessions', lambda: data)
    monkeypatch.setattr(app, 'save_sessions', lambda value: None)
    app.app.config.update(TESTING=True, SECRET_KEY='test')
    with app.app.test_client() as client:
        _login(client)
        bad_time = deepcopy(original[:1])
        bad_time[0]['slots'][0]['end'] = '08:00'
        for planning in ([{'date': '2026-02-30', 'slots': []}], [original[0], original[0]], bad_time):
            response = client.put('/api/sessions/a3p-edit/a3p-planning', json={'planningData': planning, 'saveDraft': True})
            assert response.status_code == 400
            assert session['a3pPlanningData'] == original
            assert 'a3pPlanningEditorDraft' not in session


@pytest.mark.parametrize('weekend_date', ['2026-03-07', '2026-03-08'])
def test_a3p_editor_can_save_weekend_and_generate_real_planning_pdf(monkeypatch, tmp_path, weekend_date):
    session = _session()
    changed = deepcopy(session['a3pPlanningData'])
    changed[0]['date'] = weekend_date
    data = {'sessions': [session], 'jurys': []}
    monkeypatch.setattr(app, 'load_sessions', lambda: data)
    monkeypatch.setattr(app, 'save_sessions', lambda value: None)
    monkeypatch.setattr(app, 'load_formateurs', lambda: [])
    monkeypatch.setattr(app, 'A3P_DOC_DIR', str(tmp_path))
    app.app.config.update(TESTING=True, SECRET_KEY='test')
    with app.app.test_client() as client:
        _login(client)
        response = client.put('/api/sessions/a3p-edit/a3p-planning', json={
            'planningData': changed, 'saveDraft': True, 'regeneratePdf': True,
        })
        assert response.status_code == 200, response.json
        assert response.json['isDraft'] is False
        assert response.json['needsRegeneration'] is False
        assert response.json['summary']['totalHours'] == 328
        reloaded = client.get('/api/sessions/a3p-edit/a3p-planning').json
        assert reloaded['validationErrors'] == []
        assert any(day['date'] == weekend_date for day in reloaded['planningData'])
    pdf = tmp_path / 'planning_a3p_session_a3p-edit.pdf'
    assert pdf.read_bytes().startswith(b'%PDF')
    from pypdf import PdfReader
    pdf_text = '\n'.join(page.extract_text() or '' for page in PdfReader(pdf).pages)
    assert dt.date.fromisoformat(weekend_date).strftime('%d/%m/%Y') in pdf_text
