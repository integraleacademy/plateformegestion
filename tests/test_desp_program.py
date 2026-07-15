from datetime import date
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desp_program import (
    DESP_ELEARNING_HOURS,
    DESP_PRESENTIEL_HOURS,
    DESP_TOTAL_HOURS,
    desp_program_totals,
    desp_summary_from_planning,
    generate_desp_planning,
)


def _valid_planning():
    return generate_desp_planning(
        date(2026, 1, 5),
        date(2026, 2, 6),
        date(2026, 2, 9),
        date(2026, 2, 20),
        trainer="DUPONT Jean",
        room="Salle 1",
        exam_iso="2026-02-23",
    )


def test_desp_program_totals_are_exact():
    assert desp_program_totals() == {
        "elearning": DESP_ELEARNING_HOURS,
        "presentiel": DESP_PRESENTIEL_HOURS,
        "total": DESP_TOTAL_HOURS,
    }
    assert DESP_ELEARNING_HOURS == 174
    assert DESP_PRESENTIEL_HOURS == 70
    assert DESP_TOTAL_HOURS == 244


def test_desp_planning_order_totals_exam_and_daily_limit():
    planning = _valid_planning()
    summary = desp_summary_from_planning(planning)
    assert summary["errors"] == []
    assert summary["modality_totals"] == {"elearning": 174.0, "presentiel": 70.0}
    assert summary["total_hours"] == 244.0
    assert all(day["date"] != "2026-02-23" for day in planning)

    first_presentiel_index = next(i for i, d in enumerate(planning) if any(s["modality"] == "presentiel" for s in d["slots"]))
    assert all(s["modality"] == "elearning" for d in planning[:first_presentiel_index] for s in d["slots"])
    assert all(s["modality"] == "presentiel" for d in planning[first_presentiel_index:] for s in d["slots"])
    assert max(sum(s["durationMinutes"] for s in day["slots"]) for day in planning) <= 7 * 60
    assert summary["warnings"] == []


def test_desp_excludes_weekends_and_french_holidays():
    planning = generate_desp_planning(
        date(2026, 4, 20),
        date(2026, 5, 28),
        date(2026, 5, 29),
        date(2026, 6, 12),
        trainer="DUPONT Jean",
        room="Salle 1",
        exam_iso="2026-06-15",
    )
    dates = {day["date"] for day in planning}
    assert "2026-05-01" not in dates
    assert "2026-05-08" not in dates
    assert all(date.fromisoformat(day["date"]).weekday() < 5 for day in planning)


def test_desp_short_period_generates_with_overtime_warnings():
    planning = generate_desp_planning(
        date(2026, 1, 5),
        date(2026, 1, 9),
        date(2026, 1, 12),
        date(2026, 1, 16),
        exam_iso="2026-01-19",
    )
    summary = desp_summary_from_planning(planning)
    assert summary["errors"] == []
    assert summary["modality_totals"] == {"elearning": 174.0, "presentiel": 70.0}
    assert summary["warnings"]
    assert max(sum(s["durationMinutes"] for s in day["slots"]) for day in planning) > 7 * 60
    assert {day["date"] for day in planning} <= {
        "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
        "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16",
    }
