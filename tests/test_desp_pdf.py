from datetime import date
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desp_program import generate_desp_planning, desp_summary_from_planning
from app import generate_aps_planning_pdf


def _session():
    return {"id":"desp-test","formation":"DESP","date_debut":"2026-06-01","date_fin":"2026-07-30","date_exam":"2026-07-31","salle":"Salle DESP"}


def _pdf(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    planning = generate_desp_planning(date(2026,6,1), date(2026,7,3), date(2026,7,20), date(2026,7,30), "DUPONT Jean", "Salle DESP", exam_iso="2026-07-31", allow_saturday=False)
    summary = desp_summary_from_planning(planning)
    out = tmp_path / "planning_desp.pdf"
    generate_aps_planning_pdf(_session(), "DUPONT Jean", str(out), planning_data=planning, planning_mode="desp", document_profile={"validate":"desp", "summary":summary, "planning_title":"PLANNING DE FORMATION DESP", "short_label":"DESP"})
    reader = pypdf.PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return out, reader, text


def test_desp_pdf_header_duration_format_and_pagination(tmp_path):
    out, reader, text = _pdf(tmp_path)
    assert out.exists() and out.stat().st_size > 0
    assert "Dirigeant d’une société de sécurité privée (DESP)" in text
    assert "Formation mixte — 244 heures" in text
    assert "Distanciel : 174h" in text and "Présentiel : 70h" in text and "Total : 244h" in text
    assert "Agent de Prévention et de Sécurité" not in text
    assert "175 heures" not in text and "Présentiel : 175h" not in text
    assert not re.search(r"\b\d+\.\d+h\b", text)
    assert f"Page {len(reader.pages)} / {len(reader.pages)}" in text


def test_desp_pdf_clean_times_summary_and_wrapping_smoke(tmp_path):
    _out, _reader, text = _pdf(tmp_path)
    ranges = re.findall(r"\b\d{2}:(\d{2})\s*-\s*\d{2}:(\d{2})", text)
    assert ranges and {m for pair in ranges for m in pair} <= {"00", "30"}
    assert "Synthèse des heures" in text
    assert "réglementation relative" in text or "acquisition" in text
    assert "TOTAL : 244h" in text
    # Smoke check: the long titles are emitted once as text content rather than truncated away.
    assert "Réceptionner et répondre d’un point de vue pratique" in text
