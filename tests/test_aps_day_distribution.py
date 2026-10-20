from collections import Counter
from copy import deepcopy
from datetime import date

import pytest

import app
from services.aps_day_distribution import grouped_day_minutes


def modules(*durations):
    return [{"uv": f"UV{i}", "durationMinutes": minutes} for i, minutes in enumerate(durations, 1)]


def test_moves_time_between_days_instead_of_adding_an_avoidable_third_uv():
    # Filling the first day to its old 3h target would involve UV1, UV2 and UV3.
    # Moving an hour to the next day fits all four modules in two pairs.
    assert grouped_day_minutes(modules(90, 30, 90, 90), [180, 180], [180, 120]) == [120, 180]


def test_third_uv_is_used_when_the_available_dates_make_it_unavoidable():
    assert grouped_day_minutes(modules(60, 60, 60), [180], [180]) == [180]
    with pytest.raises(ValueError, match="trois UV maximum"):
        grouped_day_minutes(modules(60, 60, 60, 60), [240], [240])


def test_counts_uvs_not_sequences_and_keeps_the_exact_minutes():
    sequence = [
        {"uv": "UV1", "durationMinutes": 45},
        {"uv": "UV1", "durationMinutes": 75},
        {"uv": "UV2", "durationMinutes": 60},
    ]
    original = deepcopy(sequence)
    assert grouped_day_minutes(sequence, [180], [180]) == [180]
    assert sequence == original


@pytest.mark.parametrize("mode,end", [
    ("full_presentiel", None),
    ("elearning_presentiel", None),
    ("elearning_presentiel", date(2026, 8, 11)),  # 16 on-site days, 8h needed
    ("elearning_presentiel", date(2026, 8, 12)),  # 17 on-site days
    ("elearning_presentiel", date(2026, 8, 13)),  # 18 on-site days
    ("elearning_presentiel", date(2026, 8, 14)),  # more time available
])
def test_generated_plans_keep_one_or_two_uvs_and_the_complete_programme(mode, end):
    planning, _, total = app.build_aps_planning_data(
        date(2026, 7, 8), "Jean Dupont", "Salle 1", mode,
        end_date=end, exam_iso="2026-08-17",
    )
    assert total == 175
    assert planning[0]["date"] == "2026-07-08"
    if end:
        assert planning[-1]["date"] == end.isoformat()
    assert all(1 <= len({slot["uv"] for slot in day["slots"]}) <= 2 for day in planning)
    assert all(app.is_aps_training_day(date.fromisoformat(day["date"]), "2026-08-17") for day in planning)
    errors, _ = app.validate_aps_planning_data(planning, mode)
    assert errors == []
    if mode == "elearning_presentiel":
        by_key = Counter()
        seen_order = []
        for day in planning:
            for slot in day["slots"]:
                key = slot["pedagogicalKey"]
                by_key[key] += slot["durationMinutes"]
                if not seen_order or seen_order[-1] != key:
                    seen_order.append(key)
        reference = app.APS_ELEARNING_PRESENTIEL_MODULES
        assert by_key == {item["key"]: item["durationMinutes"] for item in reference}
        assert seen_order == [item["key"] for item in reference]


@pytest.mark.parametrize("mode", ["full_presentiel", "elearning_presentiel"])
def test_creation_and_regeneration_after_reset_use_the_grouped_distribution(monkeypatch, tmp_path, mode):
    record = {"id": "grouped-aps", "formation": "APS", "date_debut": "2026-07-08",
              "date_fin": "2026-08-14", "date_exam": "2026-08-17", "notes": "À conserver"}
    data = {"sessions": [record], "jurys": []}
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    monkeypatch.setattr(app, "PLANNING_DIR", str(tmp_path))
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
            session["admin_session_version"] = app.ADMIN_SESSION_VERSION
        payload = {"planningMode": mode, "trainer": "Jean Dupont", "room": "Salle 1"}
        for attempt in range(2):
            response = client.post("/api/sessions/grouped-aps/generate-aps-planning", json=payload)
            assert response.status_code == 200, response.get_json()
            plan = record["apsPlanningData"]
            assert all(len({slot["uv"] for slot in day["slots"]}) <= 2 for day in plan)
            assert record["apsPlanningSummary"]["total_hours"] == 175
            assert (tmp_path / record["planning_pdf"]).exists()
            if attempt == 0:
                generated = deepcopy(plan)
                response = client.delete("/api/sessions/grouped-aps/aps-planning")
                assert response.status_code == 200
                assert "apsPlanningData" not in record
                assert record["notes"] == "À conserver"
            else:
                assert plan == generated
