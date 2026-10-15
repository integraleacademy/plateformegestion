from copy import deepcopy

import pytest

import app


def _slot(empty=False, start="08:30", end="12:00"):
    return {
        "start": start, "end": end, "durationMinutes": 210, "duration": 3.5,
        "uv": "" if empty else "UV4", "title": "" if empty else "Stratégique",
        "modality": "presentiel", "room": "Salle 1", "trainer": "Formateur",
        "isEmpty": empty,
    }


@pytest.fixture
def editor(monkeypatch):
    record = {
        "id": "aps-day-deletion", "formation": "APS", "date_exam": "2026-12-01",
        "apsPlanningMode": "full_presentiel",
        "apsPlanningData": [
            {"date": "2026-11-18", "slots": [_slot()]},
            {"date": "2026-11-19", "slots": [_slot(True), _slot(True, "13:30", "16:30")]},
            {"date": "2026-11-20", "slots": [_slot(True)]},
        ],
    }
    data = {"sessions": [record], "jurys": []}
    saved = []
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: saved.append(deepcopy(value)))
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        yield client, record, saved


@pytest.mark.parametrize("removed_index", [0, 1])
def test_deleted_day_stays_absent_after_save_and_reload(editor, removed_index):
    """Both a course day and a day of availability can be removed entirely."""
    client, record, saved = editor
    endpoint = f"/api/sessions/{record['id']}/aps-planning"
    original = client.get(endpoint).get_json()["apsPlanningData"]
    changed = deepcopy(original)
    removed = changed.pop(removed_index)
    response = client.put(endpoint, json={"planningData": changed})
    assert response.status_code == 200
    refreshed = client.get(endpoint).get_json()
    assert refreshed["apsPlanningData"] == changed
    assert saved[-1]["sessions"][0]["apsPlanningData"] == changed
    assert removed["date"] not in {day["date"] for day in refreshed["dayAvailability"]}
    assert refreshed["needsRegeneration"] is True
    uv4 = next(item for item in refreshed["curriculum"]["contents"] if item["key"] == "UV4")
    assert uv4["remainingMinutes"] == (420 if removed_index == 0 else 210)


def test_removing_last_available_slot_removes_only_its_day(editor):
    client, record, saved = editor
    endpoint = f"/api/sessions/{record['id']}/aps-planning"
    changed = deepcopy(record["apsPlanningData"])
    changed[1]["slots"].pop(0)
    changed[2]["slots"].clear()
    response = client.put(endpoint, json={"planningData": changed})
    assert response.status_code == 200
    refreshed = client.get(endpoint).get_json()
    assert [day["date"] for day in refreshed["apsPlanningData"]] == ["2026-11-18", "2026-11-19"]
    assert len(refreshed["apsPlanningData"][1]["slots"]) == 1
    assert refreshed["apsPlanningData"][1]["slots"][0]["start"] == "13:30"
    assert refreshed["curriculum"]["plannedMinutes"] == 210


def test_empty_draft_can_be_saved_repeatedly_but_cannot_be_exported(editor):
    client, record, saved = editor
    endpoint = f"/api/sessions/{record['id']}/aps-planning"
    for _ in range(2):
        response = client.put(endpoint, json={"planningData": []})
        assert response.status_code == 200
        refreshed = client.get(endpoint).get_json()
        assert refreshed["apsPlanningData"] == []
        assert refreshed["dayAvailability"] == []
        assert refreshed["compliance"]["ok"] is False
        assert refreshed["curriculum"]["plannedMinutes"] == 0
        assert refreshed["curriculum"]["remainingMinutes"] == refreshed["curriculum"]["expectedMinutes"]
        assert refreshed["pdfUrl"] is None
    assert client.put(endpoint, json={"planningData": [], "regeneratePdf": True}).status_code == 400
    assert saved[-1]["sessions"][0]["apsPlanningData"] == []


def test_edit_still_requires_an_existing_planning(editor):
    client, record, saved = editor
    record.pop("apsPlanningData")
    response = client.put(f"/api/sessions/{record['id']}/aps-planning", json={"planningData": []})
    assert response.status_code == 400
    assert saved == []
