from copy import deepcopy
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import re
import sys

import pytest
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from services.session_location import DEFAULT_TRAINING_LOCATION, training_location, update_training_location

OLD = "Ancien centre"
NEW = "Centre Paris – 14 Villa de Lourcine – 75014 Paris"


def example(formation="APS"):
    slot = {"start": "09:00", "end": "12:00", "durationMinutes": 180, "room": OLD,
            "trainer": "Alice", "uv": "UV2", "title": "Cours personnalisé", "notes": "Conserver", "modality": "presentiel"}
    plan = [{"date": "2026-11-03", "slots": [deepcopy(slot), {**slot, "room": "Terrain spécialisé"},
             {**slot, "modality": "elearning"}, {**slot, "uv": "EXAM_APS"},
             {**slot, "room": ""}, {**slot, "part": "EXAMEN SSIAP 1"}]},
            {"date": "2026-12-09", "exam": True, "slots": [deepcopy(slot)]}]
    record = {"id": "venue", "formation": formation, "date_debut": "2026-11-03", "date_fin": "2026-12-08",
              "date_exam": "2026-12-09", "salle": OLD, "steps": [], "planning_pdf": "old.pdf",
              "exam_room": OLD, "apsPlanningData": plan, "apsPlanningSummary": {"total_hours": 175},
              "apsTrainerContracts": [{"status": "signed", "interventions": deepcopy(plan)}]}
    if formation == "A3P":
        record.pop("apsPlanningData")
        record.update(a3pRoom=OLD, a3pPlanningData=plan, a3pPlanningEditorDraft=deepcopy(plan),
                      a3pPlanningBuilder={"scheduleConfig": {"room": OLD, "days": [{"date": "2026-11-03"}],
                                          "lockedModules": {"UV1": [deepcopy(slot)]}}, "preview": deepcopy(plan)},
                      a3pPlanningDraftJson={"room": OLD, "lockedModules": {"UV1": [deepcopy(slot)]}},
                      a3pTrainerManualModulesData={"UV1": [deepcopy(slot)]})
    return record


def setup_store(monkeypatch, tmp_path, record):
    monkeypatch.setattr(app, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(app, "PLANNING_DIR", str(tmp_path))
    monkeypatch.setattr(app, "A3P_DOC_DIR", str(tmp_path))
    app.save_sessions({"sessions": [record, {"id": "untouched", "formation": "APS", "salle": OLD}], "jurys": []})
    app.app.config.update(TESTING=True, SECRET_KEY="test-location")
    client = app.app.test_client()
    with client.session_transaction() as session:
        session["admin_logged"] = True
        session["admin_session_version"] = app.ADMIN_SESSION_VERSION
    return client


def form(client, location=NEW):
    response = client.get("/sessions/venue/edit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    return {"location": location, "previous_location": OLD, "csrf_token": token}


def no_build(*args, **kwargs):
    raise AssertionError("Changing the venue must never call a scheduling engine")


@pytest.mark.parametrize("formation", ["APS", "DESP", "DIRIGEANT", "SSIAP", "SSIAP1", "AFC_APS_SSIAP", "A3P"])
def test_save_preserves_all_timetable_fields_custom_rooms_remote_exams_and_other_sessions(monkeypatch, tmp_path, formation):
    before = example(formation)
    client = setup_store(monkeypatch, tmp_path, before)
    (tmp_path / "old.pdf").write_bytes(b"Existing document")
    for name in ("build_aps_planning_data", "build_ssiap1_planning_data", "build_afc_aps_ssiap_planning_data",
                 "generate_desp_planning", "generateA3pSchedule", "generate_aps_planning_pdf", "generate_a3p_planning_pdf"):
        monkeypatch.setattr(app, name, no_build)
    response = client.post("/sessions/venue/location", data=form(client))
    assert response.status_code == 302
    assert response.location.endswith("#location-section")
    records = app.load_sessions()["sessions"]
    saved = records[0]
    key = "a3pPlanningData" if formation == "A3P" else "apsPlanningData"
    expected = deepcopy(before[key])
    expected[0]["slots"][0]["room"] = NEW
    expected[0]["slots"][4]["room"] = NEW
    assert saved[key] == expected
    assert saved["salle"] == saved["room"] == NEW
    assert saved["exam_room"] == OLD
    for field in ("date_debut", "date_fin", "date_exam", "steps", "apsPlanningSummary", "apsTrainerContracts"):
        assert saved[field] == before[field]
    assert records[1] == {"id": "untouched", "formation": "APS", "salle": OLD}
    assert (tmp_path / "old.pdf").read_bytes() == b"Existing document"
    if formation == "A3P":
        assert saved["a3pRoom"] == NEW
        assert saved["a3pPlanningBuilder"]["preview"] == expected
        assert saved["a3pPlanningEditorDraft"] == expected
        assert saved["a3pPlanningBuilder"]["scheduleConfig"]["room"] == NEW
        assert saved["a3pPlanningBuilder"]["scheduleConfig"]["lockedModules"]["UV1"][0]["room"] == NEW
        assert saved["a3pPlanningDraftJson"]["room"] == NEW
        assert saved["a3pTrainerManualModulesData"]["UV1"][0]["room"] == NEW


@pytest.mark.parametrize("location", ["", "   ", "x" * 301, "bad\x00value"])
def test_invalid_location_does_not_save(monkeypatch, tmp_path, location):
    client = setup_store(monkeypatch, tmp_path, example())
    before = Path(app.SESSIONS_FILE).read_bytes()
    response = client.post("/sessions/venue/location", data=form(client, location))
    assert response.status_code == 302
    assert Path(app.SESSIONS_FILE).read_bytes() == before


def test_authentication_csrf_stale_form_and_unknown_session(monkeypatch, tmp_path):
    client = setup_store(monkeypatch, tmp_path, example())
    before = Path(app.SESSIONS_FILE).read_bytes()
    payload = form(client)
    assert client.post("/sessions/venue/location", data={**payload, "csrf_token": "wrong"}).status_code == 403
    assert client.post("/sessions/venue/location", data={**payload, "csrf_token": "invalide-é"}).status_code == 403
    assert client.post("/sessions/venue/location", data={**payload, "previous_location": "stale"}).status_code == 409
    assert client.post("/sessions/missing/location", data=payload).status_code == 404
    with client.session_transaction() as session:
        session.clear()
    assert client.post("/sessions/venue/location", data=payload).status_code == 302
    assert Path(app.SESSIONS_FILE).read_bytes() == before


def test_default_room_no_planning_and_a3p_draft_fallback():
    empty = {"formation": "APS"}
    assert training_location(empty) == DEFAULT_TRAINING_LOCATION
    assert update_training_location(empty, "  Nouveau\ncentre  ")
    assert empty == {"formation": "APS", "salle": "Nouveau centre", "room": "Nouveau centre"}
    draft = {"formation": "A3P", "a3pPlanningBuilder": {"scheduleConfig": {"room": OLD}}}
    assert training_location(draft) == OLD
    update_training_location(draft, NEW)
    assert draft["a3pPlanningBuilder"]["scheduleConfig"]["room"] == NEW


def full_session(formation):
    result = {"id": "venue", "formation": formation, "salle": OLD, "planning_pdf": "old.pdf"}
    if formation == "DESP":
        result.update(date_debut="2026-06-12", date_fin="2026-07-30", date_exam="2026-07-31", apsPlanningMode="desp")
        plan = app.generate_desp_planning(date(2026, 6, 12), date(2026, 7, 17), date(2026, 7, 20), date(2026, 7, 30), "Alice", OLD, exam_iso="2026-07-31")
    elif formation == "SSIAP":
        result.update(date_debut="2026-01-05", date_fin="2026-01-20", date_exam="2026-01-21", apsPlanningMode="ssiap1")
        plan = app.build_ssiap1_planning_data(date(2026, 1, 5), "Alice", OLD, end_date=date(2026, 1, 20), exam_iso="2026-01-21",
                                            exam_payload={"date": "2026-01-21", "start": "08:30", "end": "12:30", "room": "Salle Examen", "durationMinutes": 240})[0]
    elif formation == "AFC_APS_SSIAP":
        interruptions = [(date(2026, 12, 23), date(2027, 1, 4))]
        plan = app.build_afc_aps_ssiap_planning_data(date(2026, 11, 16), "Alice", OLD, interruptions)
        result.update(date_debut="2026-11-16", date_fin=plan[-1]["date"], date_exam=plan[-1]["date"], apsPlanningMode="full_presentiel", interruptions="23/12/2026 au 04/01/2027")
    elif formation == "A3P":
        current = date(2026, 1, 5)
        days = []
        while len(days) < 48:
            if current.weekday() < 5:
                days.append({"date": current.isoformat(), "dayStart": "08:30", "dayEnd": "16:30"})
            current += timedelta(days=1)
        days[10]["dayEnd"] = "12:30"
        days[-1].update(dayStart="10:00", dayEnd="14:00")
        config = {"room": OLD, "trainerFirstName": "Alice", "days": days, "examDate": "2026-04-30", "lockedModules": {
            "UV1": [d["date"] for d in days[:2]], "UV5": [
                {"date": days[2]["date"], "start": "08:30", "end": "12:00", "durationMinutes": 210},
                {"date": days[2]["date"], "start": "13:00", "end": "16:30", "durationMinutes": 210},
                {"date": days[3]["date"], "start": "08:30", "end": "12:00", "durationMinutes": 210},
                {"date": days[3]["date"], "start": "13:00", "end": "15:30", "durationMinutes": 150}],
            "UV6A": [d["date"] for d in days[4:11]], "UV9": [d["date"] for d in days[11:13]],
        }}
        plan = app.generateA3pSchedule(config)["planning"]
        result.update(date_debut=days[0]["date"], date_fin=days[-1]["date"], date_exam="2026-04-30", a3pRoom=OLD, a3pPlanningFilename="old.pdf")
    else:
        result.update(date_debut="2026-11-03", date_fin="2026-12-08", date_exam="2026-12-09", apsPlanningMode="elearning_presentiel")
        plan = app.normalize_aps_slot_durations(app.build_aps_planning_data(date(2026, 11, 3), "Alice", OLD, "elearning_presentiel", end_date=date(2026, 12, 8), exam_iso="2026-12-09")[0])
    result["a3pPlanningData" if formation == "A3P" else "apsPlanningData"] = plan
    return result


@pytest.mark.parametrize("formation", ["APS", "DESP", "SSIAP", "AFC_APS_SSIAP", "A3P"])
def test_pdf_uses_new_address_and_exact_saved_timetable(monkeypatch, tmp_path, formation):
    record = full_session(formation)
    client = setup_store(monkeypatch, tmp_path, record)
    (tmp_path / "old.pdf").write_bytes(b"Previous PDF")
    payload = form(client)
    for name in ("build_aps_planning_data", "build_ssiap1_planning_data", "build_afc_aps_ssiap_planning_data", "generate_desp_planning", "generateA3pSchedule"):
        monkeypatch.setattr(app, name, no_build)
    assert client.post("/sessions/venue/location", data=payload).status_code == 302
    key = "a3pPlanningData" if formation == "A3P" else "apsPlanningData"
    saved_plan = deepcopy(app.load_sessions()["sessions"][0][key])
    url = "/sessions/venue/a3p-documents/planning/view" if formation == "A3P" else "/sessions/venue/planning/view"
    response = client.get(url)
    assert response.status_code == 200, response.get_data(as_text=True)[:1000]
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.data)).pages)
    assert "Villa de Lourcine" in text
    assert "no-store" in response.headers["Cache-Control"]
    saved = app.load_sessions()["sessions"][0]
    assert saved[key] == saved_plan
    assert not saved.get("trainingLocationPdfPending")


def test_pdf_render_failure_keeps_saved_location_and_previous_file(monkeypatch, tmp_path):
    record = example("A3P")
    record["a3pPlanningFilename"] = "old.pdf"
    client = setup_store(monkeypatch, tmp_path, record)
    original = b"Previous PDF"
    (tmp_path / "old.pdf").write_bytes(original)
    client.post("/sessions/venue/location", data=form(client))
    def fail(*args):
        raise ValueError("Planning incomplet")
    monkeypatch.setattr(app, "generate_a3p_planning_pdf", fail)
    response = client.get("/sessions/venue/a3p-documents/planning/view")
    assert response.status_code == 409
    saved = app.load_sessions()["sessions"][0]
    assert saved["salle"] == NEW and saved["trainingLocationPdfPending"]
    assert (tmp_path / "old.pdf").read_bytes() == original
    assert list(tmp_path.glob("location_*.pdf")) == []
