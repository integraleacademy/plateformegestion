from datetime import date, datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from app import (
    AFC_APS_SSIAP_EXPECTED_MINUTES,
    AFC_CATEGORY_COLORS,
    AFC_TECHNICAL_CODES,
    build_afc_aps_ssiap_planning_data,
    afc_aps_ssiap_summary_from_data,
    is_french_working_day,
)


def _minutes(value):
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def test_afc_aps_ssiap_reference_case_dates_hours_and_limits():
    interruption = [(date(2026, 12, 23), date(2027, 1, 4))]
    planning = build_afc_aps_ssiap_planning_data(date(2026, 11, 16), "Formateur", "Salle", interruption)
    summary = afc_aps_ssiap_summary_from_data(planning, interruption)

    assert summary["errors"] == []
    assert planning[0]["date"] == "2026-11-16"
    assert planning[-1]["date"] == "2027-02-15"
    assert "2027-01-05" in {day["date"] for day in planning}
    assert "2027-02-11" in {day["date"] for day in planning}
    assert "2027-02-12" in {day["date"] for day in planning}
    assert all(day["date"] <= "2027-02-15" for day in planning)
    assert summary["total_hours"] == 393
    assert summary["uv_totals"] == {code: minutes / 60 for code, minutes in AFC_APS_SSIAP_EXPECTED_MINUTES.items()}
    def day_minutes(cat):
        return {day["date"]: sum(slot["durationMinutes"] for slot in day["slots"] if slot["afcCategory"] == cat) for day in planning if any(slot["afcCategory"] == cat for slot in day["slots"])}
    assert sum(day_minutes("APS").values()) == AFC_APS_SSIAP_EXPECTED_MINUTES["APS"]
    sst_days = [day for day in planning if any(slot["uv"] == "UV1" and "SST" in slot["title"] for slot in day["slots"])]
    assert sst_days
    assert sum(day_minutes("EXAM_APS").values()) == 420
    assert sum(day_minutes("H0B0").values()) == 420
    assert list(day_minutes("EXAM_SSIAP1").values()) == [420]
    assert next(iter(day_minutes("EXAM_SSIAP1"))) == planning[-1]["date"]
    assert all("None" not in str(slot) for day in planning for slot in day["slots"])

    first_week = [day for day in planning if "2026-11-16" <= day["date"] <= "2026-11-20"]
    assert sum(slot["durationMinutes"] for day in first_week for slot in day["slots"]) == 35 * 60
    assert {slot["afcCategory"] for day in first_week for slot in day["slots"]} == {"RAN"}
    for date_value in ("2026-11-23", "2026-11-24"):
        day = next(item for item in planning if item["date"] == date_value)
        assert {slot["afcCategory"] for slot in day["slots"]} == {"RAN"}
    ran_slots = [slot for day in planning for slot in day["slots"] if slot["afcCategory"] == "RAN"]
    assert ran_slots[-1]["end"] == "15:30"
    accueil_day = next(day for day in planning if day["date"] == "2026-11-26")
    assert [slot["afcCategory"] for slot in accueil_day["slots"][:1]] == ["ACCUEIL"]
    assert accueil_day["slots"][0]["start"] == "08:30" and accueil_day["slots"][0]["end"] == "12:00"
    assert [(slot["start"], slot["end"], slot["afcCategory"]) for slot in accueil_day["slots"][:2]] == [("08:30", "12:00", "ACCUEIL"), ("12:00", "12:30", "APS")]
    flattened = [(day["date"], slot["start"], slot["end"], slot["afcCategory"]) for day in planning for slot in day["slots"]]
    assert next(item for item in flattened if item[3] == "APS")[:2] == ("2026-11-26", "12:00")
    first_sp = next(item for item in flattened if item[3] == "SP")
    assert first_sp[:2] == ("2026-11-30", "08:30")
    assert first_sp[0] != accueil_day["date"]
    assert first_sp[0] != next(item for item in flattened if item[3] == "APS")[0]
    aps_before_first_sp = sum(
        slot["durationMinutes"]
        for day in planning
        for slot in day["slots"]
        if slot["afcCategory"] == "APS" and (day["date"], slot["start"]) < first_sp[:2]
    )
    assert aps_before_first_sp >= 7 * 60
    assert any(
        sum(slot["durationMinutes"] for slot in day["slots"] if slot["afcCategory"] == "APS") == 7 * 60
        for day in planning
        if day["date"] < first_sp[0]
    )
    assert flattened[-1][3] == "EXAM_SSIAP1"

    weekly = {}
    for day in planning:
        day_date = datetime.strptime(day["date"], "%Y-%m-%d").date()
        assert is_french_working_day(day_date)
        assert not (date(2026, 12, 23) <= day_date <= date(2027, 1, 4))
        intervals = []
        day_total = 0
        for slot in day["slots"]:
            start = _minutes(slot["start"])
            end = _minutes(slot["end"])
            duration = slot["durationMinutes"]
            assert end > start
            assert end - start == duration
            assert (8 * 60 + 30 <= start < end <= 12 * 60 + 30) or (13 * 60 + 30 <= start < end <= 16 * 60 + 30)
            assert not (start < 13 * 60 + 30 and end > 12 * 60 + 30)
            assert all(not (start < old_end and end > old_start) for old_start, old_end in intervals)
            intervals.append((start, end))
            day_total += duration
            bucket = weekly.setdefault(day_date.isocalendar()[:2], {"total": 0, "technical": 0, "SP": 0, "PAF": 0})
            bucket["total"] += duration
            if slot["afcCategory"] in AFC_TECHNICAL_CODES:
                bucket["technical"] += duration
            if slot["afcCategory"] in {"SP", "PAF"}:
                bucket[slot["afcCategory"]] += duration
        assert day_total <= 7 * 60
    for bucket in weekly.values():
        assert bucket["total"] <= 35 * 60
        assert bucket["technical"] <= 30 * 60
        assert bucket["SP"] <= 5 * 60
        assert bucket["PAF"] <= 5 * 60


def test_afc_reuses_detailed_aps_and_ssiap_sequences():
    planning = build_afc_aps_ssiap_planning_data(date(2026, 11, 16), "Formateur", "Salle", [(date(2026, 12, 23), date(2027, 1, 4))])
    titles = [slot["title"] for day in planning for slot in day["slots"]]
    uvs = {slot["uv"] for day in planning for slot in day["slots"]}
    assert any("ENVIRONNEMENT JURIDIQUE" in title for title in titles)
    assert "LE FEU" in titles
    assert "P1-S1" in uvs


def test_afc_pdf_generation_adds_landscape_calendar_and_headers(tmp_path):
    from pypdf import PdfReader
    from app import generate_aps_planning_pdf

    interruption = [(date(2026, 12, 23), date(2027, 1, 4))]
    planning = build_afc_aps_ssiap_planning_data(date(2026, 11, 16), "Formateur", "Salle", interruption)
    summary = afc_aps_ssiap_summary_from_data(planning, interruption)
    output = tmp_path / "afc.pdf"
    session = {
        "formation": "AFC_APS_SSIAP",
        "training_code": "AFC_APS_SSIAP",
        "display_name": "AFC France Travail APS + SSIAP",
        "date_debut": "2026-11-16",
        "date_fin": planning[-1]["date"],
        "salle": "Salle",
        "interruptions": "23/12/2026 au 04/01/2027",
    }
    generate_aps_planning_pdf(session, "Formateur", str(output), planning_data=planning, document_profile={"validate": "afc_aps_ssiap", "summary": summary})
    reader = PdfReader(str(output))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "PLANNING AFC FRANCE TRAVAIL APS + SSIAP" in text
    assert "Parcours complet" in text
    assert "AFC France Travail APS + SSIAP" in text
    assert "Agent de Prévention et de Sécurité" not in text
    assert "CALENDRIER RÉCAPITULATIF" in text
    assert "AFC FRANCE TRAVAIL APS + SSIAP" in text
    assert "Novembre 2026" in text and "Février 2027" in text and "Mars 2027" not in text
    assert "November" not in text and "March" not in text
    assert set(AFC_CATEGORY_COLORS) == set(AFC_APS_SSIAP_EXPECTED_MINUTES)
    assert "RAN" in text and "PAF" in text and "Bilan" in text
    last = reader.pages[-1].mediabox
    assert float(last.width) > float(last.height)


def test_afc_generation_route_allows_last_planning_day_as_exam_date(tmp_path, monkeypatch):
    import app as application

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    session = {
        "id": "afc-reference",
        "formation": "AFC_APS_SSIAP",
        "training_code": "AFC_APS_SSIAP",
        "display_name": "AFC France Travail APS + SSIAP",
        "date_debut": "2026-11-16",
        "interruptions": "23/12/2026 au 04/01/2027",
    }
    saved = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(application, "load_sessions", lambda: saved)
    monkeypatch.setattr(application, "save_sessions", lambda data: saved.update(data))
    monkeypatch.setattr(application, "PLANNING_DIR", str(tmp_path))

    with application.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = application.ADMIN_SESSION_VERSION
        response = client.post(
            "/api/sessions/afc-reference/generate-aps-planning",
            json={
                "trainer": "VAILLANT Clément",
                "room": "Intégrale Academy – 54 chemin du Carreou – 83480 PUGET-SUR-ARGENS",
                "interruptions": "23/12/2026 au 04/01/2027",
                "contractual_end_date": "2027-02-15",
            },
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert session["date_exam"] == "2027-02-15"
    assert session["date_fin"] == "2027-02-15"
    assert session["contractual_end_date"] == "2027-02-15"
    assert session["apsPlanningSummary"]["total_hours"] == 393


def test_afc_attendance_pdf_hides_students_before_individual_start_date(tmp_path):
    from pypdf import PdfReader
    from app import generate_aps_attendance_pdf

    output = tmp_path / "afc_attendance.pdf"
    session = {
        "id": "afc-attendance",
        "formation": "AFC_APS_SSIAP",
        "training_code": "AFC_APS_SSIAP",
        "display_name": "AFC France Travail APS + SSIAP",
        "date_debut": "2026-11-16",
        "date_fin": "2026-11-17",
        "date_exam": "2026-11-17",
        "salle": "Salle AFC",
        "apsPlanningMode": "full_presentiel",
        "apsPlanningData": [
            {"date": "2026-11-16", "slots": [{"start": "08:30", "end": "12:30", "duration": 4, "uv": "RAN", "title": "RAN", "content": "Accueil", "trainer": "Formateur", "room": "Salle AFC", "modality": "presentiel"}]},
            {"date": "2026-11-17", "slots": [{"start": "08:30", "end": "12:30", "duration": 4, "uv": "APS", "title": "APS", "content": "Module APS", "trainer": "Formateur", "room": "Salle AFC", "modality": "presentiel"}]},
        ],
        "apsAttendanceStudents": [
            {"lastName": "PREMIER", "firstName": "Alice", "startDate": "2026-11-16"},
            {"lastName": "RETARD", "firstName": "Bruno", "startDate": "2026-11-17"},
        ],
    }

    generate_aps_attendance_pdf(session, str(output))

    reader = PdfReader(str(output))
    first_day_text = reader.pages[0].extract_text() or ""
    second_day_text = reader.pages[1].extract_text() or ""
    assert "PREMIER" in first_day_text
    assert "RETARD" not in first_day_text
    assert "PREMIER" in second_day_text
    assert "RETARD" in second_day_text
