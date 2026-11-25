from copy import deepcopy
from types import SimpleNamespace
import pytest
import app as host
from services import session_catalogue as cat


def test_create_update_read_and_visibility(monkeypatch):
    data = {"sessions": []}
    monkeypatch.setattr(host, "load_sessions", lambda: deepcopy(data))
    monkeypatch.setattr(host, "save_sessions", lambda value: data.update(value))
    monkeypatch.setenv("SESSION_CATALOG_TOKEN", "test-read")
    host.app.config.update(TESTING=True, SECRET_KEY="test")
    client = host.app.test_client()
    url = "/api/integrations/session-catalogue"
    assert client.get(url).status_code == 401
    with client.session_transaction() as session:
        session.update(admin_logged=True, admin_session_version=host.ADMIN_SESSION_VERSION)
    fields = dict(formation="SSIAP", ssiap_level="3", date_debut="2098-01-05", date_fin="2098-02-05",
                  date_exam="2098-02-06", catalogue_capacity="10", catalogue_visibility="public")
    assert client.post("/sessions/create", data=fields).status_code == 302
    sid = data["sessions"][0]["id"]
    headers = {"Authorization": "Bearer test-read"}
    res = client.get(url, headers=headers)
    row, = res.json["sessions"]
    assert (row["slug"], row["capacity"], row["centre"]) == ("ssiap-3", 10, "puget")
    assert "jurys" not in row and "steps" not in row
    assert client.get(url,headers={**headers,"If-None-Match":res.headers["ETag"]}).status_code == 304
    assert client.post(f"/sessions/{sid}/edit", data={**fields,"date_exam":"2098-02-07","catalogue_visibility":"internal"}).status_code == 302
    after, = client.get(url, headers=headers).json["sessions"]
    assert after["id"] == sid and after["aliases"][0]["exam"] == "2098-02-06" and after["visibility"] == "internal"
    assert client.post(f"/sessions/{sid}/edit",data={**fields,"catalogue_capacity":"80"}).status_code == 302
    assert data["sessions"][0]["catalogue_capacity"] == 10


def test_reserved_and_general_never_publish():
    base=dict(id="reserved",date_debut="2098-02-01", date_fin="2098-03-01", formation="AFC_APS_SSIAP")
    result=cat.rows(host,[base,{**base,"id":"internal","formation":"GENERAL"}])
    assert len(result)==1 and result[0]["visibility"]=="internal"
