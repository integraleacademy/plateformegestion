import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as application


def test_delete_jury_removes_legacy_numeric_identifier(monkeypatch):
    """A jury id coming from the URL is always a string."""
    saved = {
        "sessions": [
            {
                "id": "session-1",
                "jurys": [
                    {"id": 42, "nom": "Fernandez", "prenom": "Bruno"},
                    {"id": "43", "nom": "Oberle", "prenom": "Nicolas"},
                ],
            }
        ],
        "jurys": [],
    }
    persisted = []
    monkeypatch.setattr(application, "load_sessions", lambda: saved)
    monkeypatch.setattr(application, "save_sessions", lambda data: persisted.append(data))

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    with application.app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
            session["admin_session_version"] = application.ADMIN_SESSION_VERSION
        response = client.post("/sessions/session-1/jury/42/delete")

    assert response.status_code == 302
    assert [jury["id"] for jury in saved["sessions"][0]["jurys"]] == ["43"]
    assert persisted == [saved]
