import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as application


class SavedSessions:
    def __init__(self):
        self.data = {"sessions": []}


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
