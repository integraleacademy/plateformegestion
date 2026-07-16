import pytest

import app


def session(code, **extra):
    data = {"id": f"S-{code}", "formation": code, "date_debut": "2026-09-01", "date_fin": "2026-09-30", "date_exam": "2026-10-01"}
    data.update(extra)
    return data


def test_normalize_training_code_is_strict_and_does_not_match_prefix_contamination():
    assert app.normalize_training_code(session("APS")) == "APS"
    assert app.normalize_training_code(session("A3P")) == "A3P"
    assert app.normalize_training_code(session("SSIAP")) == "SSIAP1"
    assert app.normalize_training_code(session("DIRIGEANT")) == "DESP"
    assert app.normalize_training_code({"training_code": "APS", "formation": "SSIAP"}) == "APS"
    with pytest.raises(ValueError, match="type de formation"):
        app.normalize_training_code(session("SSIAP APS"))


def test_planning_builder_matrix_selects_only_declared_training_engine():
    cases = {"APS": app.build_aps_session_planning, "A3P": app.build_a3p_planning, "SSIAP": app.build_ssiap_planning, "DIRIGEANT": app.build_desp_planning}
    for code, expected in cases.items():
        normalized, builder = app.select_training_builder(session(code), app.PLANNING_BUILDERS)
        assert builder is expected
        assert normalized in app.PLANNING_BUILDERS
    assert app.select_training_builder(session("APS"), app.PLANNING_BUILDERS)[1] is not app.build_ssiap_planning
    assert app.select_training_builder(session("APS"), app.PLANNING_BUILDERS)[1] is not app.build_a3p_planning
    assert app.select_training_builder(session("APS"), app.PLANNING_BUILDERS)[1] is not app.build_desp_planning


def test_presence_builder_matrix_selects_only_declared_training_engine():
    cases = {"APS": app.build_aps_presence_days, "A3P": app.build_a3p_presence_days, "SSIAP": app.build_ssiap_presence_days, "DIRIGEANT": app.build_desp_presence_days}
    for code, expected in cases.items():
        normalized, builder = app.select_training_builder(session(code), app.PRESENCE_BUILDERS)
        assert builder is expected
        assert normalized in app.PRESENCE_BUILDERS
    assert app.select_training_builder(session("APS"), app.PRESENCE_BUILDERS)[1] is not app.build_ssiap_presence_days


def test_presence_day_filters_are_isolated_by_training_code():
    aps = session("APS", apsPlanningMode="full_presentiel", apsPlanningData=[{"date":"2026-09-01","slots":[{"uv":"UV1","title":"APS", "duration":7,"modality":"presentiel"}]}])
    ssiap = session("SSIAP", apsPlanningData=[{"date":"2026-09-01","slots":[{"uv":"P1-S1","title":"SSIAP", "duration":7,"modality":"presentiel"}]}])
    desp = session("DIRIGEANT", apsPlanningData=[{"date":"2026-09-01","slots":[{"uv":"DESP-E01","title":"DESP E", "duration":7,"modality":"elearning"}]},{"date":"2026-09-02","slots":[{"uv":"DESP-P01","title":"DESP P", "duration":7,"modality":"presentiel"}]}])
    assert app.PRESENCE_BUILDERS["APS"](aps)[0]["slots"][0]["uv"] == "UV1"
    assert app.PRESENCE_BUILDERS["SSIAP1"](ssiap)[0]["slots"][0]["uv"] == "P1-S1"
    desp_days = app.PRESENCE_BUILDERS["DESP"](desp)
    assert len(desp_days) == 1
    assert desp_days[0]["slots"][0]["uv"] == "DESP-P01"
    assert "DESP-E01" not in str(desp_days)
