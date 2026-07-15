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
    return {"date": "2026-01-20", "start": "08:30", "end": "12:30", "room": "Salle Examen", "durationMinutes": 240}


def test_ssiap1_planning_totals_sequences_order_and_exam_exclusion():
    planning, totals, total_hours = build_ssiap1_planning_data(
        date(2026, 1, 5),
        "Jean Dupont",
        "Salle 1",
        end_date=date(2026, 1, 19),
        exam_iso="2026-01-20",
        exam_payload=_exam(),
        excluded_dates=["2026-01-14"],
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
    assert sum(slot["duration"] for day in planning for slot in day["slots"] if slot["modality"] != "exam") == 67


def test_ssiap1_planning_uses_clean_half_hour_boundaries_and_weekdays():
    planning, _, _ = build_ssiap1_planning_data(
        date(2026, 1, 5),
        "Jean Dupont",
        "Salle 1",
        end_date=date(2026, 1, 19),
        exam_iso="2026-01-20",
        exam_payload=_exam(),
        excluded_dates=["2026-01-14"],
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


def test_ssiap1_october_2026_requires_user_selected_non_training_days_and_keeps_end_dates():
    with pytest.raises(ValueError, match="Veuillez sélectionner 2 jours sans formation"):
        build_ssiap1_planning_data(
            date(2026, 10, 12),
            "Jean Dupont",
            "Salle 1",
            end_date=date(2026, 10, 27),
            exam_iso="2026-10-28",
            exam_payload={"date": "2026-10-28", "start": "08:30", "end": "16:30", "room": "Salle Examen", "durationMinutes": 480},
        )

    planning, _, _ = build_ssiap1_planning_data(
        date(2026, 10, 12),
        "Jean Dupont",
        "Salle 1",
        end_date=date(2026, 10, 27),
        exam_iso="2026-10-28",
        exam_payload={"date": "2026-10-28", "start": "08:30", "end": "16:30", "room": "Salle Examen", "durationMinutes": 480},
        excluded_dates=["2026-10-14", "2026-10-21"],
    )
    formation_days = [day for day in planning if not day.get("exam")]
    daily_minutes = {day["date"]: sum(slot["durationMinutes"] for slot in day["slots"]) for day in formation_days}

    assert len(formation_days) == 10
    assert daily_minutes["2026-10-26"] == 420
    assert daily_minutes["2026-10-27"] == 240
    assert planning[-1]["date"] == "2026-10-28"
    assert set(daily_minutes) == {"2026-10-12", "2026-10-13", "2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27"}
    assert ssiap1_summary_from_data(planning)["errors"] == []
