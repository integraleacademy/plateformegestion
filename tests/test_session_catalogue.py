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


def test_existing_public_form_group_is_attached_once_and_respects_later_withdrawal():
    from services import published_schedule_import as migration
    row = dict(id="7b549596", formation="APS", date_debut="2027-02-04", date_fin="2027-03-10", date_exam="2027-03-11")
    for existing, expected in (({}, "public"), ({"catalogue_visibility":"internal"}, "internal"), ({"archived":True}, None)):
        group = {**row, **existing}
        data = {"sessions":[group], migration.RECEIPT:{}}
        assert migration.adopt_public_form_session(host,data,"2026-11-25")
        assert group.get("catalogue_visibility")==expected and len(data["sessions"])==1
        group["catalogue_visibility"]="internal"
        assert not migration.adopt_public_form_session(host,data,"2026-11-25")
        assert group["catalogue_visibility"]=="internal"


def test_card_name_scope_modification_and_durable_deletion(monkeypatch):
    data = {"sessions":[]}
    monkeypatch.setattr(host, "load_sessions", lambda:deepcopy(data))
    monkeypatch.setattr(host, "save_sessions", lambda new:data.update(new))
    monkeypatch.setenv("SESSION_CATALOG_TOKEN","local-test")
    client = host.app.test_client()
    with client.session_transaction() as auth:
        auth.update(admin_logged=True, admin_session_version=host.ADMIN_SESSION_VERSION, session_location_csrf="local-csrf")
    fields = dict(formation="APS", session_name="Promotion Atlas", date_debut="2098-03-03",date_fin="2098-04-04",
                  date_exam="2098-04-07",remote_start="2098-03-03",remote_end="2098-03-20",catalogue_scope_form="1")
    assert client.post("/sessions/create",data=fields).status_code==302
    sid=data["sessions"][0]["id"]
    def feed():
        return client.get("/api/integrations/session-catalogue",headers={"Authorization":"Bearer local-test"}).get_json()
    page=client.get("/sessions?statut=toutes").get_data(as_text=True)
    assert f'data-gestion-only="/sessions/{sid}/gestion-stagiaires-only"' in page and "Promotion Atlas</a>" in page
    assert feed()["sessions"][0]["name"]=="Promotion Atlas"
    headers={"X-CSRF-Token":"local-csrf"}
    url=f"/sessions/{sid}/gestion-stagiaires-only"
    assert client.post(url,json={"enabled":True}).status_code==403
    assert client.post(url,json={"enabled":"false"},headers=headers).status_code==400
    for enabled in (True,True,False):
        assert client.post(url,json={"enabled":enabled},headers=headers).json["enabled"] is enabled
        group,=feed()["sessions"]
        assert group["gestion_only"] is enabled and group["visibility"]=="public"
    assert client.post(f"/sessions/{sid}/rename",json={"name":"Promotion Iris"}).json["name"]=="Promotion Iris"
    changed={**fields,"session_name":"Promotion Iris","date_debut":"2098-05-03","date_fin":"2098-06-04","date_exam":""}
    assert client.post(f"/sessions/{sid}/edit",data=changed).status_code==302
    group,=feed()["sessions"]
    assert (group["name"],group["remote_start"],group["remote_end"],group["exam"])==("Promotion Iris","2098-05-03","2098-05-20","")
    assert group["aliases"][0]["start"]==fields["date_debut"]
    assert client.post(f"/sessions/{sid}/edit",data={**changed,"date_debut":"","date_fin":"","remote_start":"","remote_end":""}).status_code==302
    assert feed()["sessions"][0]["unscheduled"]
    assert client.post(f"/sessions/{sid}/delete").status_code==302
    for _ in range(2):
        payload=feed()
        assert payload["present_ids"]==[] and len(payload["sessions"])==1
        retired,=payload["sessions"]
        assert retired["deleted"] and retired["visibility"]=="closed" and not retired["name"]
        assert {k["start"] for k in retired["aliases"]}=={fields["date_debut"],changed["date_debut"]}


def test_liste_complete_et_session_generale_reservee():
    general=dict(id="general",formation="GENERAL",date_debut="2098-02-01",date_fin="2098-03-03",display_name="Réunion interne")
    cat.set_gestion_only(general,True)
    group,=cat.rows(host,[general])
    assert group["slug"]=="general" and group["gestion_only"] and group["name"]=="Réunion interne"
    cat.set_gestion_only(general,False)
    assert cat.rows(host,[general])[0]["deleted"]


def test_renommer_une_ancienne_fiche_conserve_le_centre_et_le_niveau(monkeypatch):
    periods = dict(date_debut="2098-03-01",date_fin="2098-04-01")
    data={"sessions":[dict(periods,id="p",formation="DIRIGEANT",display_name="DESP Paris"),
                      dict(periods,id="s",formation="SSIAP",display_name="SSIAP 3")]}
    monkeypatch.setattr(host,"load_sessions",lambda:deepcopy(data))
    monkeypatch.setattr(host,"save_sessions",lambda value:data.update(value))
    client=host.app.test_client()
    with client.session_transaction() as auth:
        auth.update(admin_logged=True,admin_session_version=host.ADMIN_SESSION_VERSION)
    for sid in ("p","s"):
        assert client.post(f"/sessions/{sid}/rename",json={"name":"Promotion Atlas"}).json["ok"]
    paris, ssiap=cat.rows(host,data["sessions"])
    assert (paris["centre"],ssiap["slug"])==("paris","ssiap-3")
    assert paris["name"]==ssiap["name"]=="Promotion Atlas"
