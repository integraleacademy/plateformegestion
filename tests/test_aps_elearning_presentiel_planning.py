from datetime import date

import pytest

from app import (
    APS_ELEARNING_HOURS,
    APS_PRESENTIEL_HOURS,
    APS_TOTAL_HOURS,
    aps_summary_from_data,
    generate_aps_planning_pdf,
    generateApsElearningPresentielPlanning,
)


def test_aps_elearning_presentiel_uses_training_end_and_keeps_exam_separate():
    planning, _, total_hours = generateApsElearningPresentielPlanning(
        date(2026, 7, 1),
        "Jean Dupont",
        "Salle 1",
        end_date=date(2026, 8, 14),
        exam_iso="2026-08-17",
    )

    assert total_hours == APS_TOTAL_HOURS
    assert planning[0]["date"] == "2026-07-01"
    assert planning[-1]["date"] == "2026-08-14"
    assert all(day["date"] != "2026-08-17" for day in planning)

    elearning_slots = [slot for day in planning for slot in day["slots"] if slot["modality"] == "elearning"]
    presentiel_slots = [slot for day in planning for slot in day["slots"] if slot["modality"] == "presentiel"]

    assert sum(slot["duration"] for slot in elearning_slots) == APS_ELEARNING_HOURS
    assert sum(slot["duration"] for slot in presentiel_slots) == APS_PRESENTIEL_HOURS
    assert all(slot["trainer"] == "" and slot["room"] == "" for slot in elearning_slots)
    assert all(slot["trainer"] == "Jean Dupont" and slot["room"] == "Salle 1" for slot in presentiel_slots)
    assert max(day["date"] for day in planning if any(slot["modality"] == "elearning" for slot in day["slots"])) < min(
        day["date"] for day in planning if any(slot["modality"] == "presentiel" for slot in day["slots"])
    )


def test_aps_elearning_presentiel_extends_last_presentiel_day_when_standard_capacity_is_short():
    planning, _, total_hours = generateApsElearningPresentielPlanning(
        date(2026, 7, 8),
        "Jean Dupont",
        "Salle 1",
        end_date=date(2026, 8, 12),
    )

    presentiel_days = [day for day in planning if any(slot["modality"] == "presentiel" for slot in day["slots"])]
    presentiel_hours_by_day = [
        sum(slot["durationMinutes"] for slot in day["slots"] if slot["modality"] == "presentiel") / 60
        for day in presentiel_days
    ]

    assert total_hours == APS_TOTAL_HOURS
    assert len(presentiel_days) == 16
    assert sum(presentiel_hours_by_day) == APS_PRESENTIEL_HOURS
    assert presentiel_hours_by_day.count(7) == 15
    assert presentiel_hours_by_day[-1] == 8
    assert max(presentiel_hours_by_day) <= 8
    assert presentiel_days[-1]["slots"][-1]["end"] == "17:30"


def test_aps_elearning_presentiel_blocks_only_when_extended_capacity_is_short():
    try:
        generateApsElearningPresentielPlanning(
            date(2026, 7, 10),
            "Jean Dupont",
            "Salle 1",
            end_date=date(2026, 8, 12),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Le planning devrait être impossible même à 8h/jour.")

    assert "98 heures disponibles à 7h/jour" in message
    assert "112 heures maximum à 8h/jour" in message
    assert "113 heures nécessaires" in message


def test_mixed_aps_summary_keeps_elearning_and_presentiel_modules_separate():
    planning, _, _ = generateApsElearningPresentielPlanning(
        date(2026, 7, 8), "Jean Dupont", "Salle 1", end_date=date(2026, 8, 12)
    )

    summary = aps_summary_from_data(planning)

    assert sum(row["hours"] for row in summary["uv_rows"] if row["modality"] == "elearning") == APS_ELEARNING_HOURS
    assert sum(row["hours"] for row in summary["uv_rows"] if row["modality"] == "presentiel") == APS_PRESENTIEL_HOURS
    assert {row["modality"] for row in summary["uv_rows"]} == {"elearning", "presentiel"}
    assert any(row["uv"] == "UV2" and row["modality"] == "elearning" for row in summary["uv_rows"])
    assert any(row["uv"] == "UV2" and row["modality"] == "presentiel" for row in summary["uv_rows"])


def test_mixed_aps_pdf_summary_has_no_sst_heading_and_lists_both_modalities(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    planning, _, _ = generateApsElearningPresentielPlanning(
        date(2026, 7, 8), "Jean Dupont", "Salle 1", end_date=date(2026, 8, 12)
    )
    output = tmp_path / "planning_aps_mixte.pdf"

    generate_aps_planning_pdf(
        {
            "id": "aps-mixte-test",
            "formation": "APS",
            "date_debut": "2026-07-08",
            "date_fin": "2026-08-12",
            "date_exam": "2026-08-13",
            "salle": "Salle 1",
        },
        "Jean Dupont",
        str(output),
        planning_data=planning,
        planning_mode="elearning_presentiel",
    )

    text = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(str(output)).pages)
    assert "A. SST" not in text
    assert "E-learning / distanciel : 62h" in text
    assert "Présentiel : 113h" in text
    assert "UV2 — Environnement juridique de la sécurité privée" in text
    assert "E-learning" in text and "Présentiel" in text
