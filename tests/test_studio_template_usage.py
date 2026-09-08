import concurrent.futures
from services.studio_usage_service import load_template_usage, set_template_usage


def test_usage_survives_new_connections_and_is_isolated_by_admin(tmp_path):
    assert load_template_usage(tmp_path, "first") == {}
    original = set_template_usage(tmp_path, "first", "carousel_aps_1", True)
    assert "carousel_aps_1" in load_template_usage(tmp_path, "first")
    assert load_template_usage(tmp_path, "second") == {}
    assert set_template_usage(tmp_path, "first", "carousel_aps_1", True) == original
    assert set_template_usage(tmp_path, "first", "carousel_aps_1", False) == {}


def test_concurrent_updates_do_not_overwrite_other_templates(tmp_path):
    load_template_usage(tmp_path, "admin")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: set_template_usage(tmp_path, "admin", f"template_{i}", True), range(30)))
    assert len(load_template_usage(tmp_path, "admin")) == 30


def test_usage_api_auth_validation_and_round_trip(tmp_path, monkeypatch):
    import app as application
    monkeypatch.setattr(application, "DATA_DIR", str(tmp_path))
    client = application.app.test_client()
    assert client.get("/api/admin/studio/template-usage").status_code == 302
    assert client.post("/api/admin/studio/template-usage", json={}).status_code == 302
    with client.session_transaction() as session:
        session["admin_logged"] = True
        session["admin_session_version"] = application.ADMIN_SESSION_VERSION
        session["admin_email"] = "usage-test"
    url = "/api/admin/studio/template-usage"
    headers = {"X-Requested-With": "XMLHttpRequest"}
    assert client.post(url, json={"templateId": "carousel_aps_1", "used": True}).status_code == 403
    for payload in ([], {"templateId": "missing", "used": True}, {"templateId": "carousel_aps_1", "used": "true"}):
        assert client.post(url, json=payload, headers=headers).status_code == 400
    response = client.post(url, json={"templateId": "carousel_aps_1", "used": True}, headers=headers)
    assert response.status_code == 200
    assert "carousel_aps_1" in client.get(url).json["used"]
    assert client.post(url, json={"templateId": "carousel_aps_1", "used": False}, headers=headers).json["used"] == {}
