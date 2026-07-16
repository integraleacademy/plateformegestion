from datetime import date
import inspect
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
from desp_program import DESP_ELEARNING_HOURS, DESP_PRESENTIEL_HOURS, DESP_TOTAL_HOURS, generate_desp_planning, desp_summary_from_planning
from app import generate_aps_planning_pdf


def _session():
    return {"id":"desp-test","formation":"DESP","date_debut":"2026-06-12","date_fin":"2026-07-30","date_exam":"2026-07-31","salle":"Salle DESP"}


def _planning():
    return generate_desp_planning(date(2026,6,12), date(2026,7,17), date(2026,7,20), date(2026,7,30), "BRUANT Christophe", "Salle DESP", exam_iso="2026-07-31", allow_saturday=False)


def _pdf(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    planning = _planning()
    summary = desp_summary_from_planning(planning)
    out = tmp_path / "planning_desp.pdf"
    generate_aps_planning_pdf(_session(), "BRUANT Christophe", str(out), planning_data=planning, planning_mode="desp", document_profile={"validate":"desp", "summary":summary, "planning_title":"PLANNING DE FORMATION DESP", "short_label":"DESP"})
    reader = pypdf.PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return out, reader, text, planning, summary


def test_desp_and_aps_share_the_same_pdf_renderer_components():
    src = inspect.getsource(app.generate_aps_planning_pdf)
    assert "planning_pdf_profile" in src
    assert "planning_card_height" in src
    assert "planning_day_height" in src
    assert "draw_legend" in src
    assert "summary_table_header" in src


def test_shared_layout_constants_match_aps_reference():
    src = inspect.getsource(app.generate_aps_planning_pdf)
    assert "margin = 36" in src
    assert "height - 72, width=72, height=49" in src
    assert '"Helvetica-Bold", 16' in src
    assert '"Helvetica", 9' in src
    assert "signature_box_h = 92" in src


def test_desp_pdf_header_legend_dates_totals_and_pagination(tmp_path):
    out, reader, text, _planning, _summary = _pdf(tmp_path)
    assert out.exists() and out.stat().st_size > 0
    assert "PLANNING DE FORMATION DESP" in text
    assert "Dirigeant d’une société de sécurité privée (DESP) — 244 heures" in text
    assert "Modalité : E-learning + présentiel" in text
    assert "E-learning : 174h" in text and "Présentiel : 70h" in text and "Total : 244h" in text
    assert "Formation mixte — 244 heures" not in text
    assert "Distanciel : 174h • Présentiel : 70h" not in text
    assert "Légende" in text
    assert "E-learning / distanciel — 174h" in text
    assert "Présentiel au centre — 70h" in text
    assert "Vendredi 12 Juin 2026" in text
    assert "Lundi 20 Juillet 2026" in text
    assert not re.search(r"Vendredi\s+12/06/2026", text)
    assert f"Page {len(reader.pages)} / {len(reader.pages)}" in text


def test_desp_card_geometry_prevents_title_time_badge_overlap():
    long = {"uv":"DESP-P01", "title":"Connaître le positionnement de la sécurité privée dans l’architecture globale de sécurité", "modality":"presentiel"}
    very_long = {**long, "title": long["title"] + " et assurer une coordination opérationnelle claire avec les autorités compétentes"}
    printable_width = 523.2755905511812
    assert app.planning_card_height(very_long, printable_width) > app.planning_card_height(long, printable_width)
    title_width = printable_width - 225
    for line in app.wrap_text_lines(app.planning_slot_title(very_long), title_width, "Helvetica-Bold", 8.2):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        assert stringWidth(line, "Helvetica-Bold", 8.2) <= title_width


def test_desp_summary_table_columns_wrapping_and_repeated_header_rules(tmp_path):
    _out, reader, text, _planning, _summary = _pdf(tmp_path)
    assert "Partie" in text and "Module" in text and "Modalité" in text and "Heures" in text
    assert "thème" not in text.lower() and "sous-thème" not in text.lower()
    assert text.count("B. Récapitulatif détaillé") >= 1
    assert "TOTAL : 244h" in text
    assert "Examen le 31/07/2026." in text
    assert len(reader.pages) >= 2


def test_desp_totals_are_preserved():
    summary = desp_summary_from_planning(_planning())
    assert summary["modality_totals"]["elearning"] == DESP_ELEARNING_HOURS
    assert summary["modality_totals"]["presentiel"] == DESP_PRESENTIEL_HOURS
    assert summary["total_hours"] == DESP_TOTAL_HOURS
    assert not summary["errors"]


def _attendance_text(tmp_path, planning=None):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    planning = planning or _planning()
    out = tmp_path / "attendance_desp.pdf"
    app.generate_aps_attendance_pdf({
        **_session(),
        "apsPlanningData": planning,
        "apsPlanningMode": "desp",
        "apsAttendanceStudents": [{"lastName": "DURAND", "firstName": "Alice"}],
        "display_name": "Session DESP test",
    }, str(out))
    reader = pypdf.PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return out, reader, text



def test_desp_attendance_renderer_resets_state_and_removes_session_background_box():
    src = inspect.getsource(app.generate_attendance_pdf_common)
    assert "def reset_graphics_state" in src
    assert "setFillAlpha(1)" in src
    assert "setStrokeAlpha(1)" in src
    assert "No filled background box here" in src
    assert "c.rect(margin, y - row_h*4 - 4" not in src
    assert "c.rect(0, 0, width, height, fill=1, stroke=0)" in src


def test_desp_attendance_renderer_forces_black_text_and_aps_table_borders():
    src = inspect.getsource(app.generate_attendance_pdf_common)
    assert "reset_graphics_state(fill=colors.black, stroke=colors.black, line_width=0.75)" in src
    assert 'reset_graphics_state(fill=colors.HexColor("#f3f4f6"), stroke=colors.black, line_width=0.75)' in src
    assert "c.rect(margin,y-18,sum(ws),18,fill=1,stroke=1)" in src
    assert "c.rect(margin,y-row_h,sum(ws),row_h)" in src


def test_desp_attendance_visible_session_fields_are_present(tmp_path):
    _out, reader, text = _attendance_text(tmp_path)
    first_page_text = reader.pages[0].extract_text() or ""
    assert "Session" in first_page_text
    assert "Date" in first_page_text
    assert "Formateur" in first_page_text
    assert "Modules et horaires du jour" in first_page_text
    assert "Session DESP test" in first_page_text
    assert "20/07/2026" in first_page_text
    assert "BRUANT Christophe" in first_page_text
    assert "DESP-P01" in text

def test_desp_attendance_generates_only_in_person_days_and_70_hours(tmp_path):
    out, reader, text = _attendance_text(tmp_path)
    assert out.exists() and out.stat().st_size > 0
    assert len(reader.pages) == 9
    assert "FEUILLE DE PRÉSENCE" in text
    assert "FEUILLE DE PRÉSENCE — FORMATION DESP" not in text
    assert "PÉRIODE PRÉSENTIELLE — 70 HEURES" not in text
    assert "Synthèse des feuilles de présence" not in text
    for label in ["20/07/2026", "21/07/2026", "22/07/2026", "23/07/2026", "24/07/2026", "27/07/2026", "28/07/2026", "29/07/2026", "30/07/2026"]:
        assert label in text
    for label in ["12/06/2026", "17/07/2026", "31/07/2026"]:
        assert f"Date : {label}" not in text
    assert "DESP-E01" not in text and "DESP-E32" not in text
    assert "DESP-P01" in text and "DESP-P21" in text
    assert not re.search(r"DESP-E\d{2}", text)


def test_desp_attendance_rejects_non_70h_presentiel_total(tmp_path):
    planning = _planning()
    planning = [{**day, "slots": [dict(slot) for slot in day["slots"]]} for day in planning]
    for day in planning:
        for slot in day["slots"]:
            if slot.get("modality") == "presentiel":
                slot["duration"] = 1
                slot["durationMinutes"] = 60
                slot["end"] = slot["start"]
                with pytest.raises(ValueError, match="planning présentiel contient"):
                    _attendance_text(tmp_path, planning)
                return
    pytest.fail("No presentiel slot found")


def test_desp_attendance_helper_excludes_empty_elearning_distance_exam_slots():
    assert app.is_in_person_slot({"modality": "presentiel"})
    assert app.is_in_person_slot({"delivery_mode": "in_person"})
    assert not app.is_in_person_slot({"modality": "elearning"})
    assert not app.is_in_person_slot({"modality": "distanciel"})
    assert not app.is_in_person_slot({"modality": "distance"})
    assert not app.is_in_person_slot({"modality": "asynchronous"})
    assert not app.is_in_person_slot({"modality": "examen"})
    assert not app.is_in_person_slot({})


def test_desp_attendance_no_blank_sheet_for_day_without_in_person_slot(tmp_path):
    planning = _planning() + [{"date": "2026-07-18", "dayLabel": "Samedi 18/07/2026", "slots": [{"start": "08:30", "end": "10:30", "duration": 2, "durationMinutes": 120, "uv": "DESP-E99", "title": "Journée vide", "modality": "elearning"}]}]
    _out, reader, text = _attendance_text(tmp_path, planning)
    assert len(reader.pages) == 9
    assert "18/07/2026" not in text
    assert "DESP-E99" not in text


def test_desp_attendance_header_layout_stays_right_of_logo():
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth

    width, height = A4
    margin = 10 * mm
    header = app.desp_attendance_header_layout(width, height, margin, stringWidth)
    logo = header["logo"]
    aps_header = app.attendance_header_layout(width, height, margin, stringWidth, subtitle="Agent de Prévention et de Sécurité (APS)")
    assert header["logo"] == aps_header["logo"]
    assert header["title"]["x"] == aps_header["title"]["x"]
    assert header["title"]["y"] == aps_header["title"]["y"]
    assert header["session_y"] == aps_header["session_y"]
    assert header["lines"][0]["text"].startswith("FEUILLE DE PRÉSENCE")
    assert "FEUILLES DE PRÉSENCE" not in header["lines"][0]["text"]
    assert "PÉRIODE PRÉSENTIELLE" not in "\n".join(line["text"] for line in header["lines"])
    assert header["session_y"] < min(line["y"] for line in header["lines"]) - 20


def test_desp_attendance_header_text_repeated_on_all_daily_pages(tmp_path):
    out, reader, _ = _attendance_text(tmp_path)
    assert out.exists()
    for page in reader.pages[:9]:
        text = page.extract_text() or ""
        assert "FEUILLE DE PRÉSENCE" in text
        assert "FEUILLE DE PRÉSENCE — FORMATION DESP" not in text
        assert "PÉRIODE PRÉSENTIELLE — 70 HEURES" not in text
        assert "Dirigeant d’une société de sécurité privée (DESP)" in text
    assert len(reader.pages) == 9
