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


def test_import_uses_published_capacity_variants_and_respects_existing_records():
    import csv
    from services import published_schedule_import as migration
    with migration.MANIFEST.open() as stream:
        offers=list(csv.DictReader(stream))
    def existing(offer, id, **meta):
        return dict(id=id, formation="APS", date_debut=offer["start"], date_fin=offer["end"], date_exam=offer["exam"], **meta)
    aps=[r for r in offers if r["slug"]=="aps"]
    current={"sessions":[existing(aps[0],"operational",notes="conserver",catalogue_capacity=8),
                         existing(aps[1],"private",catalogue_visibility="internal")]}
    assert migration.reconcile(host,current,offers,"2026-11-25")
    assert not migration.reconcile(host,current,offers,"2026-11-25")
    assert len(current["sessions"])==22
    assert current["sessions"][0]["notes"]=="conserver" and current["sessions"][0]["catalogue_capacity"]==8
    assert current["sessions"][1]["catalogue_visibility"]=="internal"
    rows=cat.rows(host,current["sessions"])
    assert len([r for r in rows if r["standard_start"]])==4
    assert [r["capacity"] for r in rows if r["slug"]=="ssiap-3"] == [10,10]


def test_save_both_dates_before_rescheduling_ssiap(monkeypatch):
    current = dict(id="groupe", formation="SSIAP", ssiap_level="1", date_debut="2098-02-05", date_fin="2098-03-12",
                   catalogue_standard_start="2098-02-09", date_exam="")
    data = {"sessions":[current]}
    monkeypatch.setattr(host,"load_sessions",lambda:deepcopy(data))
    monkeypatch.setattr(host,"save_sessions",lambda snapshot:data.update(snapshot))
    client = host.app.test_client()
    with client.session_transaction() as session:
        session.update(admin_logged=True, admin_session_version=host.ADMIN_SESSION_VERSION)
    reply=client.post("/sessions/groupe/edit",data={"date_debut":"2098-02-06","date_fin":"2098-03-12","date_exam":"","catalogue_standard_start":"2098-02-10"})
    assert reply.status_code==302
    row,=cat.rows(host,data["sessions"])
    assert row["standard_start"]=="2098-02-10" and row["aliases"][0]["standard_start"]=="2098-02-09"
