from datetime import date

import pytest

from app import (
    SSIAP1_PART_TOTALS,
    SSIAP1_SEQUENCE_TOTALS,
    SSIAP1_TOTAL_HOURS,
    build_ssiap1_planning_data,
    ssiap1_summary_from_data,
)


def _exam():
    return {"date": "2026-01-21", "start": "08:30", "end": "12:30", "room": "Salle Examen", "durationMinutes": 240}


def test_ssiap1_planning_totals_sequences_order_and_exam_exclusion():
    planning, totals, total_hours = build_ssiap1_planning_data(
        date(2026, 1, 5),
        "Jean Dupont",
        "Salle 1",
        end_date=date(2026, 1, 20),
        exam_iso="2026-01-21",
        exam_payload={**_exam(), "sstTrainer": "Sophie SST", "revisionTrainer": "Jean Dupont", "examTrainer": "Resp Examen"},
    )
    summary = ssiap1_summary_from_data(planning)

    assert total_hours == SSIAP1_TOTAL_HOURS
    assert summary["total_hours"] == SSIAP1_TOTAL_HOURS
    assert summary["errors"] == []
    assert totals == SSIAP1_SEQUENCE_TOTALS
    assert len(summary["uv_rows"]) == 24
    assert [row["uv"] for row in summary["uv_rows"]] == list(SSIAP1_SEQUENCE_TOTALS)
    assert summary["part_totals"] == SSIAP1_PART_TOTALS
    assert planning[-1]["exam"] is True
    assert planning[-1]["slots"][0]["title"] == "EXAMEN SSIAP 1"
    assert planning[-1]["slots"][0]["durationMinutes"] == 240
    assert summary["exam"]["durationMinutes"] == 240
    assert sum(slot["duration"] for day in planning for slot in day["slots"] if slot["modality"] == "presentiel") == 67


def test_ssiap1_planning_uses_clean_half_hour_boundaries_and_weekdays():
    planning, _, _ = build_ssiap1_planning_data(
        date(2026, 1, 5),
        "Jean Dupont",
        "Salle 1",
        end_date=date(2026, 1, 20),
        exam_iso="2026-01-21",
        exam_payload={**_exam(), "sstTrainer": "Sophie SST", "revisionTrainer": "Jean Dupont", "examTrainer": "Resp Examen"},
    )

    formation_days = [day for day in planning if not day.get("exam")]
    assert all(date.fromisoformat(day["date"]).weekday() < 5 for day in formation_days)
    for slot in [slot for day in planning for slot in day["slots"]]:
        assert slot["start"][-2:] in {"00", "30"}
        assert slot["end"][-2:] in {"00", "30"}


def test_ssiap1_planning_refuses_short_period():
    with pytest.raises(ValueError) as exc:
        build_ssiap1_planning_data(
            date(2026, 1, 5),
            "Jean Dupont",
            "Salle 1",
            end_date=date(2026, 1, 9),
            exam_iso="2026-01-12",
            exam_payload={"date": "2026-01-12", "start": "08:30", "end": "12:30", "room": "Salle Examen", "durationMinutes": 240},
        )

    assert "nécessite exactement" in str(exc.value) or "Impossible de générer le planning" in str(exc.value)


def test_ssiap1_october_2026_places_sst_then_ssiap_and_revision_without_excluded_days():
    planning, _, _ = build_ssiap1_planning_data(
        date(2026, 10, 12),
        "Jean SSIAP",
        "Salle 1",
        end_date=date(2026, 10, 27),
        exam_iso="2026-10-28",
        exam_payload={"date": "2026-10-28", "start": "08:30", "end": "16:30", "room": "Salle Examen", "durationMinutes": 480, "sstTrainer": "Sophie SST", "revisionTrainer": "Rémi Révision", "examTrainer": "Eva Examen"},
    )
    daily_minutes = {day["date"]: sum(slot["durationMinutes"] for slot in day["slots"]) for day in planning if not day.get("exam")}
    sst_days = [day for day in planning if day.get("category") == "sst"]
    ssiap_days = [day for day in planning if day.get("category") == "ssiap1"]
    summary = ssiap1_summary_from_data(planning)

    assert [day["date"] for day in sst_days] == ["2026-10-12", "2026-10-13"]
    assert all(sum(slot["durationMinutes"] for slot in day["slots"]) == 420 for day in sst_days)
    assert [day["date"] for day in ssiap_days] == ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27"]
    assert daily_minutes["2026-10-26"] == 420
    assert daily_minutes["2026-10-27"] == 420
    assert sum(slot["durationMinutes"] for slot in ssiap_days[-1]["slots"] if slot["modality"] == "presentiel") == 240
    assert sum(slot["durationMinutes"] for slot in ssiap_days[-1]["slots"] if slot["modality"] == "revision") == 180
    assert planning[-1]["date"] == "2026-10-28"
    assert summary["sst_hours"] == 14
    assert summary["total_hours"] == 67
    assert summary["revision_hours"] == 3
    assert summary["presence_total_hours"] == 84
    assert summary["errors"] == []
    assert all(slot["trainer"] == "Sophie SST" for day in sst_days for slot in day["slots"])
    assert all(slot["trainer"] == "Rémi Révision" for slot in ssiap_days[-1]["slots"] if slot["modality"] == "revision")
    assert planning[-1]["slots"][0]["trainer"] == "Eva Examen"
