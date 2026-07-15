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
