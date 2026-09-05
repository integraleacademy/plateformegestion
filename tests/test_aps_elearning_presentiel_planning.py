from datetime import date

import pytest

from app import (
    APS_CPNEFP_PROGRAM_VERSION,
    APS_ELEARNING_HOURS,
    APS_EXPECTED_ELEARNING_UV_TOTALS,
    APS_EXPECTED_PRACTICE_UV_MINUTES,
    APS_PRACTICE_MINUTES,
    APS_PRESENTIEL_HOURS,
    APS_PRESENTIEL_THEORY_MINUTES,
    APS_TOTAL_HOURS,
    aps_summary_from_data,
    validate_aps_planning_data,
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
        end_date=date(2026, 8, 11),
    )

    presentiel_days = [day for day in planning if any(slot["modality"] == "presentiel" for slot in day["slots"])]
    presentiel_hours_by_day = [
        sum(slot["durationMinutes"] for slot in day["slots"] if slot["modality"] == "presentiel") / 60
        for day in presentiel_days
    ]

    assert total_hours == APS_TOTAL_HOURS
    assert len(presentiel_days) == 16
    assert sum(presentiel_hours_by_day) == APS_PRESENTIEL_HOURS
    assert presentiel_hours_by_day.count(7) == 4
    assert presentiel_hours_by_day.count(8) == 12
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

    assert "105 heures disponibles à 7h/jour" in message
    assert "120 heures maximum à 8h/jour" in message
    assert "124 heures nécessaires" in message


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
    assert summary["practice_hours"] == APS_PRACTICE_MINUTES / 60
    assert summary["presentiel_theory_hours"] == APS_PRESENTIEL_THEORY_MINUTES / 60
    assert summary["modality_uv_totals"]["elearning"] == APS_EXPECTED_ELEARNING_UV_TOTALS
    assert summary["practice_uv_hours"] == {
        uv: minutes / 60 for uv, minutes in APS_EXPECTED_PRACTICE_UV_MINUTES.items()
    }
    assert validate_aps_planning_data(planning, "elearning_presentiel")[0] == []


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
    assert "E-learning / distanciel : 51h" in text
    assert "Présentiel : 124h" in text
    assert "Dont pratique en présentiel : 63h30" in text
    assert "Dont théorie en présentiel : 60h30" in text
    assert f"CPNEFP {APS_CPNEFP_PROGRAM_VERSION}" in text
    assert "UV2 — Livre VI du code de la sécurité intérieure" in text
    assert "E-learning" in text and "Présentiel" in text


def test_generation_route_persists_the_cpnefp_reference(monkeypatch, tmp_path):
    import app as application

    application.app.config.update(TESTING=True, SECRET_KEY="test")
    session = {
        "id": "aps-v32-route",
        "formation": "APS",
        "date_debut": "2026-07-08",
        "date_fin": "2026-08-11",
        "date_exam": "2026-08-12",
    }
    data = {"sessions": [session], "jurys": []}
    monkeypatch.setattr(application, "load_sessions", lambda: data)
    monkeypatch.setattr(application, "save_sessions", lambda value: None)
    monkeypatch.setattr(application, "PLANNING_DIR", str(tmp_path))

    with application.app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["admin_logged"] = True
            flask_session["admin_session_version"] = application.ADMIN_SESSION_VERSION
        response = client.post(
            "/api/sessions/aps-v32-route/generate-aps-planning",
            json={"planningMode": "elearning_presentiel", "trainer": "Jean Dupont", "room": "Salle 1"},
        )

    assert response.status_code == 200
    assert session["apsPlanningReferenceVersion"] == "V3.2"
    assert session["apsPlanningReferenceDate"] == "23/07/2026"
    assert session["apsPlanningNeedsRegeneration"] is False
    assert session["apsPlanningSummary"]["modality_totals"] == {"elearning": 51.0, "presentiel": 124.0}
    assert session["apsPlanningSummary"]["practice_hours"] == 63.5
    assert (tmp_path / "planning_aps_session_aps-v32-route.pdf").exists()
