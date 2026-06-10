import json
import urllib.error

import pytest

import app as application


@pytest.fixture()
def client(monkeypatch):
    application.app.config.update(TESTING=True, SECRET_KEY="test")
    monkeypatch.setitem(application._stagiaires_docs_cache, "payload", None)
    monkeypatch.setitem(application._stagiaires_docs_cache, "retry_after", 0.0)
    with application.app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
        yield client


def test_fetch_uses_interservice_token(client, monkeypatch):
    captured = {}

    class Response:
        headers = type("Headers", (), {"get_content_charset": lambda self: "utf-8"})()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({"pending_count": 3}).encode()

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        captured["api_key"] = request.get_header("X-api-key")
        return Response()

    monkeypatch.setenv("STAGIAIRES_DOCS_TO_CONTROL_TOKEN", "shared-secret")
    monkeypatch.setattr(application.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/stagiaires/docs-to-control.json")

    assert response.status_code == 200
    assert response.get_json()["pending_count"] == 3
    assert captured == {
        "authorization": "Bearer shared-secret",
        "api_key": "shared-secret",
    }


def test_upstream_error_returns_unavailable_without_false_zero(client, monkeypatch):
    def failed_fetch(*args, **kwargs):
        raise urllib.error.HTTPError("https://example.test", 403, "Forbidden", {}, None)

    monkeypatch.setattr(application, "fetch_json_url", failed_fetch)

    response = client.get("/stagiaires/docs-to-control.json")

    assert response.status_code == 200
    assert response.get_json() == {
        "error": "Données dossiers stagiaires indisponibles",
        "items": [],
        "ok": False,
        "pending_count": None,
    }


def test_last_successful_value_is_used_during_upstream_failure(client, monkeypatch):
    responses = iter(({"pending_count": 4, "items": [{"pending_count": 4}]}, RuntimeError("offline")))

    def fetch(*args, **kwargs):
        result = next(responses)
        if isinstance(result, Exception):
            raise OSError(str(result))
        return result

    monkeypatch.setattr(application, "fetch_json_url", fetch)

    first = client.get("/stagiaires/docs-to-control.json")
    second = client.get("/stagiaires/docs-to-control.json")

    assert first.get_json()["pending_count"] == 4
    assert second.status_code == 200
    assert second.get_json()["pending_count"] == 4
    assert second.get_json()["stale"] is True


def test_upstream_error_payload_is_not_treated_as_zero(client, monkeypatch):
    monkeypatch.setattr(
        application,
        "fetch_json_url",
        lambda *args, **kwargs: {"ok": False, "error": "unauthorized"},
    )

    response = client.get("/stagiaires/docs-to-control.json")

    assert response.status_code == 200
    assert response.get_json()["ok"] is False
    assert response.get_json()["pending_count"] is None
