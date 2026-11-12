"""Calendar coverage, linked bookings, recurrence, persistence and edit safety."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

import pytest
from flask import Flask, session, redirect

from services.personal_planner import register, training_events

ROOT = "/gestion-clement-elsa"
TOKEN = "test-only-csrf"
HEADERS = {"X-Planner-CSRF": TOKEN}


@pytest.fixture
def planner(tmp_path):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.update(TESTING=True, SECRET_KEY="test-only", PERSONAL_PLANNER_DB=str(tmp_path / "planner.sqlite3"))
    sessions = {"sessions": []}

    @app.before_request
    def auth():
        if not session.get("admin_logged"):
            return redirect("/login")

    register(app, str(tmp_path), lambda: sessions, lambda s, m: s.get("onsite"))
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.update(admin_logged=True, planner_csrf=TOKEN)
    return app, client, sessions


def save(client, **record):
    response = client.post(ROOT + "/records", json=record, headers=HEADERS)
    assert response.status_code == 201, response.json
    return response.json["ids"]


def data(client, year=2027):
    response = client.get(ROOT + f"/data?year={year}")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json


def location(**overrides):
    return dict(kind="location", start="2027-01-01", end="2027-01-10", place="cantal", owner="both", **overrides)


def test_auth_csrf_and_private_page(planner):
    app, client, _ = planner
    for url in (ROOT, ROOT + "/data"):
        assert app.test_client().get(url).status_code == 302
    assert client.get(ROOT).status_code == 200
    assert client.post(ROOT + "/records", json={"kind": "note", "title": "Private"}).status_code == 403
    assert client.post(ROOT + "/records", data="invalid", headers=HEADERS).status_code == 400


def test_empty_year_leap_year_and_individual_coverage(planner):
    _, client, _ = planner
    assert data(client)["coverage"]["missing_days"] == 365
    assert data(client, 2028)["coverage"]["missing_days"] == 366
    save(client, kind="location", start="2028-02-29", end="2028-02-29", place="paris", owner="clement")
    cov = data(client, 2028)["coverage"]
    assert cov["missing_days"] == 366
    assert {"owner": "elsa", "start": "2028-02-29", "end": "2028-02-29", "count": 1} in cov["missing"]
    save(client, kind="location", start="2028-02-29", end="2028-02-29", place="cantal", owner="elsa")
    assert data(client, 2028)["coverage"]["covered_days"] == 1


def test_fill_year_preserves_stays_and_distinct_locations(planner):
    _, client, _ = planner
    first, = save(client, kind="location", start="2027-06-01", end="2027-06-10", place="paris", owner="both")
    save(client, kind="location", start="2027-07-01", end="2027-07-04", place="puget", owner="clement")
    ids = save(client, kind="location", start="2027-01-01", end="2027-12-31", place="cantal", owner="both", fill_gaps=True)
    result = data(client)
    assert result["coverage"]["missing_days"] == 0
    days = {d["date"]: d for d in result["coverage"]["days"]}
    assert days["2027-06-02"]["clement"]["id"] == first
    assert days["2027-07-02"]["clement"]["place"] == "puget"
    assert days["2027-07-02"]["elsa"]["place"] == "cantal"
    assert ids
    assert save(client, kind="location", start="2027-01-01", end="2027-12-31", place="cantal", fill_gaps=True) == []


def test_overlapping_places_rejected_without_partial_write(planner):
    _, client, _ = planner
    save(client, **location())
    conflicting = dict(location(), start="2027-01-10", end="2027-01-15", place="puget")
    r = client.post(ROOT + "/records", json=conflicting, headers=HEADERS)
    assert r.status_code == 409
    assert "10/01/2027" in r.json["error"]
    assert len(data(client)["records"]) == 1


def test_louise_fortnightly_across_year_and_series_delete(planner):
    _, client, _ = planner
    ids = save(client, kind="louise", start="2026-12-25", end="2026-12-27", repeat="fortnightly", repeat_until="2027-01-24")
    assert len(ids) == 3
    records = sorted(data(client)["records"], key=lambda r: r["start"])
    assert [(r["start"], r["end"]) for r in records] == [("2026-12-25", "2026-12-27"), ("2027-01-08", "2027-01-10"), ("2027-01-22", "2027-01-24")]
    assert len({r["series_id"] for r in records}) == 1
    first = records[0]
    r = client.put(ROOT + "/records/" + first["id"], json=dict(first, notes="Vacances"), headers=HEADERS)
    assert r.status_code == 200
    assert sum(r["notes"] == "Vacances" for r in data(client)["records"]) == 1
    r = client.delete(ROOT + "/records/" + first["id"], json={"revision": 2, "delete_series": True}, headers=HEADERS)
    assert r.json["count"] == 3
    assert data(client)["records"] == []


def test_booked_boarding_real_dates_and_flights(planner):
    _, client, _ = planner
    save(client, kind="location", place="paris", start="2027-02-08", end="2027-02-18",
         boarding_status="booked", boarding_start="2027-02-07", boarding_end="2027-02-19", boarding_notes="Pension confirmée",
         transport_status="booked", transport_start="2027-02-08", transport_end="2027-02-18", transport_origin="Nice", transport_mode="Avion")
    result = data(client)
    assert result["alerts"] == []
    bookings = sorted(result["reservations"], key=lambda r: r["start"])
    assert len(bookings) == 3
    assert bookings[0]["kind"] == "boarding"
    assert (bookings[0]["start"], bookings[0]["end"]) == ("2027-02-07", "2027-02-19")
    assert bookings[2]["destination"] == "Nice"
    assert bookings[2]["start"] == bookings[2]["end"] == "2027-02-18"
    save(client, kind="transport", start="2027-03-01", end="2027-03-01", title="Retour Puget", origin="Paris Orly", destination="Nice", status="booked")
    assert len(data(client)["reservations"]) == 4


def test_pending_bookings_and_insufficient_boarding_coverage(planner):
    _, client, _ = planner
    rid, = save(client, kind="location", place="away", destination="Londres", start="2027-01-01", end="2027-01-10")
    assert len(data(client)["alerts"]) == 2
    record = data(client)["records"][0]
    payload = dict(record, boarding_status="booked", boarding_start="2027-01-02", boarding_end="2027-01-09", transport_status="not_needed")
    assert client.put(ROOT + "/records/" + rid, json=payload, headers=HEADERS).status_code == 200
    assert len(data(client)["alerts"]) == 1
    assert "dates à vérifier" in data(client)["alerts"][0]["title"]


@pytest.mark.parametrize("record", [
    {"kind": "location", "place": "away", "start": "2027-01-01", "end": "2027-01-02"},
    {"kind": "louise", "start": "2027-02-29", "end": "2027-03-01"},
    {"kind": "louise", "start": "2027-01-08", "end": "2027-01-01"},
    {"kind": "louise", "start": "2027-01-01", "end": "2027-01-09", "repeat": "weekly", "repeat_until": "2027-02-01"},
    {"kind": "location", "place": "paris", "start": "2027-01-01", "end": "2027-01-05", "boarding_status": "booked"},
    {"kind": "location", "place": "paris", "start": "2027-01-01", "end": "2027-01-05", "fill_gaps": True},
    {"kind": "transport", "start": "2027-01-01", "end": "2027-01-01", "origin": "Paris"},
    {"kind": "note", "title": ""},
    {"kind": "note", "title": "Note", "owner": ["clement"]},
])
def test_invalid_input_is_actionable_and_atomic(planner, record):
    _, client, _ = planner
    response = client.post(ROOT + "/records", json=record, headers=HEADERS)
    assert response.status_code == 400
    assert response.json["error"]
    assert data(client)["records"] == []


def test_revisions_prevent_lost_update_and_stale_delete(planner):
    _, client, _ = planner
    rid, = save(client, kind="shopping", title="Café", quantity="2 paquets")
    original = data(client)["records"][0]
    assert client.put(ROOT + "/records/" + rid, json=dict(original, done=True), headers=HEADERS).status_code == 200
    assert client.put(ROOT + "/records/" + rid, json=dict(original, title="Thé"), headers=HEADERS).status_code == 409
    assert client.delete(ROOT + "/records/" + rid, json={"revision": 1}, headers=HEADERS).status_code == 409
    actual = data(client)["records"][0]
    assert actual["done"] is True and actual["title"] == "Café"


def test_persisted_data_visible_across_clients_and_concurrent_writes(planner):
    app, client, _ = planner
    def create_item(index):
        other = app.test_client()
        with other.session_transaction() as sess:
            sess.update(admin_logged=True, planner_csrf=TOKEN)
        return save(other, kind="note", title=f"Note {index}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(create_item, range(12)))
    assert len(data(client)["records"]) == 12
    with sqlite3.connect(app.config["PERSONAL_PLANNER_DB"]) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_training_is_live_read_only_projection_and_formats(planner):
    _, client, sessions = planner
    sessions["sessions"] = [{"id": "desp", "formation": "DESP", "date_debut": "04/01/2027", "date_fin": "2027-02-18", "date_exam": "19/02/2027", "onsite": {"start": "2027-02-08"}}]
    before = json.dumps(sessions, sort_keys=True)
    result = data(client)
    assert len(result["training"]) == 4
    assert all(r["readonly"] and r["url"] == "/sessions/desp" for r in result["training"])
    assert json.dumps(sessions, sort_keys=True) == before
    sessions["sessions"][0]["date_exam"] = "2027-02-20"
    assert next(r for r in data(client)["training"] if r["kind"] == "training_exam")["start"] == "2027-02-20"
    assert data(client)["records"] == []


def test_cannot_invent_onsite_date_for_remote_course():
    records = training_events([{"id": "1", "formation": "APS", "date_debut": "2027-01-01", "apsPlanningMode": "elearning_presentiel"}], lambda s, m: None)
    assert [r["kind"] for r in records] == ["training_start"]
    records = training_events([{"id": "2", "formation": "DESP", "date_debut": "2027-01-01", "despPresentielStart": "2027-02-01"}], lambda s, m: None)
    assert next(r for r in records if r["kind"] == "training_onsite")["start"] == "2027-02-01"


def test_session_failure_does_not_hide_personal_data(tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"
    def unavailable():
        raise OSError("unavailable")
    register(app, str(tmp_path), unavailable, lambda s, m: None)
    response = app.test_client().get(ROOT + "/data?year=2027")
    assert response.status_code == 200
    assert response.json["training_error"]
    assert response.json["coverage"]["missing_days"] == 365


def test_new_trip_splits_a_completed_year_without_losing_other_days(planner):
    _, client, _ = planner
    save(client, kind="location", place="cantal", start="2027-01-01", end="2027-12-31", notes="Lieu habituel")
    save(client, kind="location", place="paris", start="2027-06-10", end="2027-06-15", owner="clement", replace_conflicts=True)
    result = data(client)
    assert result["coverage"]["missing_days"] == 0
    days = {r["date"]: r for r in result["coverage"]["days"]}
    assert days["2027-06-12"]["clement"]["place"] == "paris"
    assert days["2027-06-12"]["elsa"]["place"] == "cantal"
    assert days["2027-06-09"]["clement"]["place"] == "cantal"
    assert days["2027-06-16"]["clement"]["place"] == "cantal"
    assert sum(r.get("notes") == "Lieu habituel" for r in result["records"]) == 3


def test_replacement_cannot_silently_remove_bookings(planner):
    _, client, _ = planner
    save(client, kind="location", place="paris", start="2027-06-10", end="2027-06-15")
    save(client, kind="location", place="cantal", start="2027-01-01", end="2027-12-31", fill_gaps=True)
    original = data(client)["records"]
    response = client.post(ROOT + "/records", json=dict(kind="location", place="puget", start="2027-06-08", end="2027-06-18", replace_conflicts=True), headers=HEADERS)
    assert response.status_code == 409
    assert data(client)["records"] == original


def test_full_app_card_guard_zoom_and_session_import(tmp_path, monkeypatch):
    import app as application
    sessions_file = tmp_path / "sessions.json"
    sessions_file.write_text(json.dumps({"sessions": [{"id": "test", "formation": "APS", "date_debut": "2027-01-01", "date_fin": "2027-02-01", "date_exam": "2027-02-02", "apsPlanningData": [{"date": "2027-01-10", "slots": [{"modality": "presentiel"}]}]}], "jurys": []}))
    monkeypatch.setattr(application, "SESSIONS_FILE", str(sessions_file))
    monkeypatch.setitem(application.app.config, "PERSONAL_PLANNER_DB", str(tmp_path / "personal.sqlite3"))
    client = application.app.test_client()
    assert client.get(ROOT + "/data").status_code == 302
    with client.session_transaction() as auth:
        auth.update(admin_logged=True, admin_session_version=application.ADMIN_SESSION_VERSION)
    assert "Gestion Clément &amp; Elsa" in client.get("/").get_data(as_text=True)
    page = client.get(ROOT).get_data(as_text=True)
    assert "global-default-zoom" not in page
    result = client.get(ROOT + "/data?year=2027").json
    assert len(result["training"]) == 4
    assert next(r for r in result["training"] if r["kind"] == "training_onsite")["start"] == "2027-01-10"


def test_corrupt_personal_store_is_not_replaced_with_empty_data(planner):
    app, client, _ = planner
    with open(app.config["PERSONAL_PLANNER_DB"], "wb") as handle:
        handle.write(b"broken-database")
    response = client.get(ROOT + "/data?year=2027")
    assert response.status_code == 503
    with open(app.config["PERSONAL_PLANNER_DB"], "rb") as handle:
        assert handle.read() == b"broken-database"
