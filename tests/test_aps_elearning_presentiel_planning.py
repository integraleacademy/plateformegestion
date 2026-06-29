from datetime import date

from app import (
    APS_ELEARNING_HOURS,
    APS_PRESENTIEL_HOURS,
    APS_TOTAL_HOURS,
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
