from collections import Counter
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as application
from services.afc_sst_planning import (
    BLOCK_FIELDS, TIME_FIELDS, group_afc_sst_days, is_afc_sst_slot,
    validate_afc_sst_days,
)

INTERRUPTIONS = [(date(2026, 12, 23), date(2027, 1, 4))]


def minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def fragmented_planning():
    """Rejouer le remplissage séquentiel responsable du SST sur quatre dates."""
    planning = application.build_afc_aps_ssiap_planning_data(date(2026, 11, 16), "Formateur", "Salle")
    modules = [dict(module, remaining=module["durationMinutes"]) for module in application.afc_build_main_sequence() if module["category"] == "APS"]
    index = 0
    for day in planning:
        windows = []
        for slot in sorted(day["slots"], key=lambda slot: slot["start"]):
            if slot["afcCategory"] != "APS":
                continue
            start = minutes(slot["start"])
            end = minutes(slot["end"])
            if windows and windows[-1][1] == start:
                windows[-1][1] = end
            else:
                windows.append([start, end])
        day["slots"] = [slot for slot in day["slots"] if slot["afcCategory"] != "APS"]
        for start, end in windows:
            while start < end:
                module = modules[index]
                duration = min(end - start, module["remaining"])
                day["slots"].append(application.afc_slot_from_module(date.fromisoformat(day["date"]), start, start + duration, module, "Formateur", "Salle"))
                module["remaining"] -= duration
                start += duration
                if not module["remaining"]:
                    index += 1
        day["slots"].sort(key=lambda slot: slot["start"])
    return planning


def content_totals(planning):
    totals = Counter()
    for day in planning:
        for slot in day["slots"]:
            ignored = TIME_FIELDS | (BLOCK_FIELDS if is_afc_sst_slot(slot) else set())
            content = {key: value for key, value in slot.items() if key not in ignored}
            totals[json.dumps(content, sort_keys=True)] += slot["durationMinutes"]
    return totals


def test_generation_reserves_two_complete_sst_days_and_keeps_all_afc_constraints():
    planning = application.build_afc_aps_ssiap_planning_data(date(2026, 11, 16), "Formateur", "Salle")
    sst = [day for day in planning if any(is_afc_sst_slot(slot) for slot in day["slots"])]
    assert [day["date"] for day in sst] == ["2026-12-09", "2026-12-10"]
    for day in sst:
        assert all(is_afc_sst_slot(slot) for slot in day["slots"])
        assert [(slot["start"], slot["end"], slot["durationMinutes"]) for slot in day["slots"]] == [("08:30", "12:30", 240), ("13:30", "16:30", 180)]
        assert all(slot["is_atomic"] and not slot["can_split"] for slot in day["slots"])
    summary = application.afc_aps_ssiap_summary_from_data(planning, INTERRUPTIONS)
    assert summary["errors"] == []
    assert summary["total_hours"] == 393 and summary["days_count"] == 57
    assert summary["uv_totals"]["APS"] == 175


def test_correction_preserves_every_module_assignment_note_and_non_aps_slot():
    before = fragmented_planning()
    sst_days = [day for day in before if any(is_afc_sst_slot(slot) for slot in day["slots"])]
    assert len(sst_days) == 4
    sst_days[0]["slots"][-1].update(trainer="Formateur SST dédié", room="Atelier", notes="Cas pratiques")
    snapshot = deepcopy(before)
    after = group_afc_sst_days(before)
    assert before == snapshot
    assert content_totals(after) == content_totals(before)
    for old, new in zip(before, after):
        assert old["date"] == new["date"]
        assert sum(slot["durationMinutes"] for slot in old["slots"]) == sum(slot["durationMinutes"] for slot in new["slots"])
        assert [slot for slot in old["slots"] if slot["afcCategory"] != "APS"] == [slot for slot in new["slots"] if slot["afcCategory"] != "APS"]
        if not "2026-12-03" <= old["date"] <= "2026-12-10":
            assert new == old
    assert application.afc_aps_ssiap_summary_from_data(after, INTERRUPTIONS)["errors"] == []
    assert group_afc_sst_days(after) == after


def test_validation_rejects_fragmentation_even_when_all_hour_totals_are_correct():
    planning = fragmented_planning()
    assert application.validate_actual_afc_hours(planning) == []
    errors = application.afc_aps_ssiap_summary_from_data(planning, INTERRUPTIONS)["errors"]
    assert any("deux journées de 7h" in error for error in errors)
    assert any("entièrement consacrée au SST" in error for error in errors)


def test_incomplete_sst_or_missing_full_days_is_never_silently_repaired():
    planning = fragmented_planning()
    incomplete = deepcopy(planning)
    slot = next(slot for day in incomplete for slot in day["slots"] if is_afc_sst_slot(slot))
    slot["uv"] = "UV7"
    with pytest.raises(ValueError, match="exactement 14h"):
        group_afc_sst_days(incomplete)
    for day in planning:
        if day["slots"] and not any(is_afc_sst_slot(slot) for slot in day["slots"]):
            day["slots"][0]["afcCategory"] = "SP"
    with pytest.raises(ValueError, match="Deux journées APS consécutives"):
        group_afc_sst_days(planning)


def saved_session(tmp_path, monkeypatch):
    planning_dir = tmp_path / "plannings"
    planning_dir.mkdir()
    monkeypatch.setattr(application, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(application, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(application, "PLANNING_DIR", str(planning_dir))
    target = {"id": "9f823786", "formation": "AFC_APS_SSIAP", "training_code": "AFC_APS_SSIAP", "date_debut": "2026-11-16", "date_fin": "2027-02-15", "date_exam": "2027-02-15", "contractual_end_date": "2027-02-15", "interruptions": "23/12/2026 au 04/01/2027", "apsPlanningData": fragmented_planning(), "planning_pdf": "old.pdf", "apsAttendanceStudents": [{"id": "student-to-preserve"}], "afcDsfs": [{"id": "dsf-to-preserve"}], "notes": "Conserver"}
    data = {"sessions": [target, {"id": "other", "formation": "APS"}], "jurys": [{"id": "jury"}]}
    application.save_sessions(data)
    (planning_dir / "old.pdf").write_bytes(b"original PDF")
    return data


def test_migration_preserves_other_data_backs_up_and_regenerates_pdf_once(tmp_path, monkeypatch):
    from pypdf import PdfReader
    before = saved_session(tmp_path, monkeypatch)
    result = application.migrate_afc_sst_session()
    assert result["sst_dates"] == ["2026-12-09", "2026-12-10"]
    assert result["hours"] == 393 and result["days"] == 57
    after = application.load_sessions()
    target = after["sessions"][0]
    assert after["sessions"][1:] == before["sessions"][1:] and after["jurys"] == before["jurys"]
    for key in ("apsAttendanceStudents", "afcDsfs", "notes", "date_exam", "date_fin"):
        assert target[key] == before["sessions"][0][key]
    assert validate_afc_sst_days(target["apsPlanningData"]) == []
    pdf = tmp_path / "plannings" / target["planning_pdf"]
    text = "\n".join(page.extract_text() for page in PdfReader(pdf).pages)
    assert "Mercredi 9 Décembre 2026" in text and "Jeudi 10 Décembre 2026" in text
    backup = next((tmp_path / "planning_migrations").rglob("*.json"))
    assert json.loads(backup.read_text()) == before["sessions"][0]
    assert backup.with_suffix(".pdf").read_bytes() == b"original PDF"
    stored, generated = Path(application.SESSIONS_FILE).read_bytes(), pdf.read_bytes()
    assert application.migrate_afc_sst_session() == {"status": "already_applied"}
    assert Path(application.SESSIONS_FILE).read_bytes() == stored and pdf.read_bytes() == generated


def test_failed_pdf_generation_keeps_saved_session_and_pdf(tmp_path, monkeypatch):
    saved_session(tmp_path, monkeypatch)
    stored = Path(application.SESSIONS_FILE).read_bytes()
    def fail(*args, **kwargs):
        raise RuntimeError("PDF indisponible")
    monkeypatch.setattr(application, "generate_aps_planning_pdf", fail)
    with pytest.raises(RuntimeError, match="PDF indisponible"):
        application.migrate_afc_sst_session()
    assert Path(application.SESSIONS_FILE).read_bytes() == stored
    assert (tmp_path / "plannings" / "old.pdf").read_bytes() == b"original PDF"
    assert not list((tmp_path / "plannings").glob("afc_sst_*"))
