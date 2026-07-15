from datetime import date
import re
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


def _valid_planning(allow_saturday=False):
    return generate_desp_planning(
        date(2026, 6, 1), date(2026, 7, 3),
        date(2026, 7, 20), date(2026, 7, 30),
        trainer="DUPONT Jean", room="Salle 1", exam_iso="2026-07-31",
        allow_saturday=allow_saturday,
    )


def _minutes(day):
    return sum(s["durationMinutes"] for s in day["slots"])


def test_desp_program_totals_are_exact():
    assert desp_program_totals() == {"elearning": DESP_ELEARNING_HOURS, "presentiel": DESP_PRESENTIEL_HOURS, "total": DESP_TOTAL_HOURS}
    assert (DESP_ELEARNING_HOURS, DESP_PRESENTIEL_HOURS, DESP_TOTAL_HOURS) == (174, 70, 244)


def test_desp_planning_fixed_day_fill_totals_minutes_and_clean_times():
    planning = _valid_planning(allow_saturday=True)
    summary = desp_summary_from_planning(planning)
    assert summary["errors"] == []
    assert summary["modality_totals"] == {"elearning": 174.0, "presentiel": 70.0}
    assert summary["total_hours"] == 244.0
    assert max(_minutes(day) for day in planning) <= 7 * 60
    assert all(re.match(r"^\d{2}:(00|30)$", s[t]) for d in planning for s in d["slots"] for t in ("start", "end"))
    assert all(float(s["duration"]).is_integer() for d in planning for s in d["slots"])


def test_desp_elearning_25_days_are_24_full_and_one_six_hour_day():
    planning = _valid_planning(allow_saturday=True)
    elearning_days = [d for d in planning if d["slots"][0]["modality"] == "elearning"]
    day_minutes = [_minutes(d) for d in elearning_days]
    assert len(elearning_days) == 25
    assert day_minutes.count(420) == 24
    assert day_minutes[-1] == 360
    assert sum(day_minutes) == 174 * 60


def test_desp_presentiel_requires_10_days_and_can_explicitly_use_saturday():
    with pytest.raises(ValueError, match="70 heures nécessitent 10 journées de 7 heures, mais seulement 9 journées"):
        _valid_planning(allow_saturday=False)
    planning = _valid_planning(allow_saturday=True)
    presentiel_days = [d for d in planning if d["slots"][0]["modality"] == "presentiel"]
    assert len(presentiel_days) == 10
    assert all(_minutes(d) == 420 for d in presentiel_days)
    assert "2026-07-25" in {d["date"] for d in presentiel_days}


def test_desp_excludes_holidays_for_distanciel():
    planning = generate_desp_planning(date(2026, 4, 20), date(2026, 5, 29), date(2026, 6, 1), date(2026, 6, 12), exam_iso="2026-06-15")
    dates = {day["date"] for day in planning}
    assert "2026-05-01" not in dates
    assert "2026-05-08" not in dates
