from datetime import date, datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from app import (
    AFC_APS_SSIAP_EXPECTED_MINUTES,
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
    assert all(day["date"] < "2027-02-16" for day in planning)
    assert summary["total_hours"] == 393
    assert summary["uv_totals"] == {code: minutes / 60 for code, minutes in AFC_APS_SSIAP_EXPECTED_MINUTES.items()}

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
        assert bucket["SP"] + bucket["PAF"] <= 5 * 60


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
    assert "Calendrier récapitulatif AFC APS + SSIAP" in text
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
            },
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert session["date_exam"] == "2027-02-15"
    assert session["date_fin"] == "2027-02-15"
    assert session["apsPlanningSummary"]["total_hours"] == 393
