import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as application
from services import shared_rooms


class SavedSessions:
    def __init__(self):
        self.data = {"sessions": []}


def test_create_a3p_offline_keeps_unassigned_exam(monkeypatch, tmp_path):
    application.app.config.update(TESTING=True, SECRET_KEY="test")
    monkeypatch.setattr(application, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(application, "IS_RENDER", False)
    monkeypatch.setenv("SHARED_ROOMS_TOKEN", "room-test")
    monkeypatch.setenv("BTS_ROOMS_URL", "https://rooms.test")

    def unavailable(*args):
        raise shared_rooms.RoomError("Planning indisponible", status=503)

    monkeypatch.setattr(shared_rooms, "call", unavailable)
    with application.app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
            session["admin_session_version"] = application.ADMIN_SESSION_VERSION

        response = client.post("/sessions/create", data={
            "formation": "A3P", "date_debut": "2027-01-11",
            "date_fin": "2027-02-26", "date_exam": "2027-03-01",
        })
        assert response.status_code == 302
        created, = application.load_sessions()["sessions"]
        assert response.location.endswith("/sessions/" + created["id"])
        assert client.get(response.location).status_code == 200

    # The calendar pulls from the same saved projection once it is available.
    item = shared_rooms.projection(created)
    assert item["metadata"]["needs_schedule"]
    assert item["slots"] == [
        {"date": "2027-03-01", "start": "00:00", "end": "24:00", "room_id": None}
    ]


def test_create_dirigeant_session_requires_location(monkeypatch):
    application.app.config.update(TESTING=True, SECRET_KEY="test")
    saved = SavedSessions()
    monkeypatch.setattr(application, "load_sessions", lambda: saved.data)
    monkeypatch.setattr(application, "save_sessions", lambda data: setattr(saved, "data", data))

    with application.app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
            session["admin_session_version"] = application.ADMIN_SESSION_VERSION

        response = client.post(
            "/sessions/create",
            data={
                "formation": "DIRIGEANT",
                "date_debut": "2026-08-01",
                "date_fin": "2026-08-05",
                "date_exam": "2026-08-06",
            },
        )

    assert response.status_code == 302
    assert saved.data == {"sessions": []}


def test_create_dirigeant_session_stores_location(monkeypatch):
    application.app.config.update(TESTING=True, SECRET_KEY="test")
    saved = SavedSessions()
    monkeypatch.setattr(application, "load_sessions", lambda: saved.data)
    monkeypatch.setattr(application, "save_sessions", lambda data: setattr(saved, "data", data))

    with application.app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
            session["admin_session_version"] = application.ADMIN_SESSION_VERSION

        response = client.post(
            "/sessions/create",
            data={
                "formation": "DIRIGEANT",
                "dirigeant_location": "puget",
                "date_debut": "2026-08-01",
                "date_fin": "2026-08-05",
                "date_exam": "2026-08-06",
            },
        )

    assert response.status_code == 302
    assert len(saved.data["sessions"]) == 1
    created = saved.data["sessions"][0]
    assert created["formation"] == "DIRIGEANT"
    assert created["dirigeant_location"] == "PUGET"
    assert created["dirigeant_location_label"] == "Puget"
