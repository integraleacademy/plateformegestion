from copy import deepcopy
from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

import app
from services.aps_pdf_presentation import compact_planning_for_pdf, module_summary_rows


def test_pdf_merges_sequences_but_keeps_breaks_teacher_changes_and_source_data():
    base = {"uv": "UV1", "title": "Titre détaillé", "modality": "presentiel",
            "trainer": "Formateur A", "room": "Salle", "part": "Présentiel"}
    slots = [
        {**base, "start": "08:30", "end": "10:30", "durationMinutes": 120, "practiceMinutes": 0},
        {**base, "start": "10:30", "end": "12:30", "durationMinutes": 120, "practiceMinutes": 120},
        {**base, "start": "13:30", "end": "14:30", "durationMinutes": 60, "practiceMinutes": 60},
        {**base, "start": "14:30", "end": "15:30", "durationMinutes": 60, "practiceMinutes": 60, "trainer": "Formateur B"},
        {**base, "start": "15:30", "end": "16:30", "durationMinutes": 60, "practiceMinutes": 0, "uv": "UV2"},
    ]
    source = [{"date": "2026-11-16", "slots": slots}]
    before = deepcopy(source)
    result = compact_planning_for_pdf(source)[0]["slots"]
    assert source == before
    assert len(result) == 4
    assert (result[0]["start"], result[0]["end"], result[0]["durationMinutes"]) == ("08:30", "12:30", 240)
    assert result[0]["practiceMinutes"] == 120
    assert result[0]["deliveryType"] == "mixed"
    assert result[0]["apsDisplayTitle"] == "UV 1 - Module Secourisme"
    assert result[1]["start"] == "13:30"
    assert result[2]["trainer"] == "Formateur B"
    assert result[3]["apsDisplayTitle"] == "UV 2 - Module Environnement juridique"


def mixed_plan():
    return app.generateApsElearningPresentielPlanning(
        date(2026, 11, 3), "Rachid EL MEHERZI", "Salle 1", end_date=date(2026, 12, 8), exam_iso="2026-12-09",
    )[0]


def test_summary_has_fourteen_modules_and_preserves_both_modalities():
    summary = app.aps_summary_from_data(mixed_plan())
    rows = module_summary_rows(summary)
    assert len(rows) == 14
    assert len({row["uv"] for row in rows}) == 14
    assert rows[0]["label"] == "UV 1 - Module Secourisme"
    assert rows[1]["elearningHours"] == 20
    assert rows[1]["presentielHours"] == 2
    assert sum(row["hours"] for row in rows) == 175
    assert sum(row["elearningHours"] for row in rows) == 51
    assert sum(row["presentielHours"] for row in rows) == 124


@pytest.mark.parametrize("mode", ["full_presentiel", "elearning_presentiel"])
@pytest.mark.parametrize("endpoint", ["view", "download"])
def test_existing_planning_pdf_refreshes_with_simple_names_without_rewriting_the_plan(monkeypatch, tmp_path, mode, endpoint):
    plan = app.normalize_aps_slot_durations(app.build_aps_planning_data(
        date(2026, 11, 3), "Rachid EL MEHERZI", "Salle 1", mode,
        end_date=date(2026, 12, 8), exam_iso="2026-12-09",
    )[0])
    original = deepcopy(plan)
    record = {"id": "simple-aps", "formation": "APS", "date_debut": "2026-11-03",
              "date_fin": "2026-12-08", "date_exam": "2026-12-09", "salle": "Salle 1",
              "apsPlanningMode": mode, "apsPlanningData": plan, "planning_pdf": "planning_aps_session_simple-aps.pdf"}
    (tmp_path / record["planning_pdf"]).write_bytes(b"Old PDF")
    data = {"sessions": [record], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    monkeypatch.setattr(app, "PLANNING_DIR", str(tmp_path))
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
            session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        response = client.get(f"/sessions/simple-aps/planning/{endpoint}")
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    reader = PdfReader(BytesIO(response.data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "UV 1 - Module Secourisme" in text
    assert "UV 2 - Module Environnement juridique" in text
    assert "Apports théoriques" not in text
    assert "Mise en situation pratique" not in text
    assert "Livre VI du code" not in text
    assert "B. Récapitulatif par module" in text
    recap = text.split("B. Récapitulatif par module", 1)[1]
    assert recap.count("UV 1 - Module Secourisme") == 1
    assert recap.count("UV 2 - Module Environnement juridique") == 1
    assert f"Page {len(reader.pages)} / {len(reader.pages)}" in text
    assert record["apsPlanningData"] == original
    assert record["apsPlanningSummary"]["total_hours"] == 175
