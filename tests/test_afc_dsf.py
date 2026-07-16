from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import (
    AFC_DSF_STATUS_CANCELLED, AFC_DSF_STATUS_FINALIZED,
    afc_dsf_compute, afc_dsf_next_number, afc_dsf_summary,
    build_afc_aps_ssiap_planning_data, generate_afc_dsf_pdf,
    is_afc_aps_ssiap_session,
)


def sample_session():
    planning = build_afc_aps_ssiap_planning_data(date(2026, 11, 16), "Formateur", "Salle", [])
    return {"id":"s1","formation":"AFC_APS_SSIAP","training_code":"AFC_APS_SSIAP","display_name":"AFC France Travail APS + SSIAP","date_debut":planning[0]["date"],"date_fin":planning[-1]["date"],"apsPlanningData":planning,"apsAttendanceStudents":[{"id":"a","lastName":"DUPONT","firstName":"Jean"},{"id":"b","lastName":"MARTIN","firstName":"Sophie"}],"afcDsfs":[]}

def test_tab_visibility_condition_exact_afc_only():
    assert is_afc_aps_ssiap_session({"formation":"AFC_APS_SSIAP"})
    assert not is_afc_aps_ssiap_session({"formation":"APS"})
    assert not is_afc_aps_ssiap_session({"formation":"SSIAP1"})
    assert not is_afc_aps_ssiap_session({"formation":"A3P"})
    assert not is_afc_aps_ssiap_session({"formation":"DIRIGEANT"})

def test_module_selection_one_or_two_and_third_refused():
    s=sample_session(); day=s["apsPlanningData"][0]["date"]
    assert afc_dsf_compute(s, day, day, ["RAN"])["totalHours"] > 0
    assert afc_dsf_compute(s, day, day, ["RAN","FT"])["totalHours"] > 0
    try: afc_dsf_compute(s, day, day, ["RAN","FT","SP"]); assert False
    except ValueError as e: assert "deux modules" in str(e)

def test_inclusive_dates_and_planning_hours_absences_ignored_no_presence_dependency():
    s=sample_session(); d=s["apsPlanningData"][0]["date"]; s["absences"]={"a":[d]}; s["presenceSheets"]="must-not-be-read"
    res=afc_dsf_compute(s,d,d,["RAN"])
    assert res["hoursPerStudent"]["RAN"] == 7
    assert res["totalHours"] == 14

def test_afc_categories_grouped_and_modules_separated():
    s=sample_session(); all_start=s["date_debut"]; all_end=s["date_fin"]
    res=afc_dsf_compute(s,all_start,all_end,["FT","RAN"])
    assert res["hoursPerStudent"]["FT"] == 273
    assert res["hoursPerStudent"]["RAN"] == 55
    assert afc_dsf_compute(s,all_start,all_end,["SP"])["hoursPerStudent"]["SP"] == 45
    assert afc_dsf_compute(s,all_start,all_end,["PAF"])["hoursPerStudent"]["PAF"] == 20

def test_totals_numbering_double_billing_cancel_and_remaining_snapshot():
    s=sample_session(); d=s["apsPlanningData"][0]["date"]
    r1=afc_dsf_compute(s,d,d,["RAN"]); assert r1["totalHours"]==14
    dsf1={"id":"1","number":1,"label":"DSF 1","status":AFC_DSF_STATUS_FINALIZED,**r1}; s["afcDsfs"].append(dsf1)
    assert afc_dsf_next_number(s)==2
    try: afc_dsf_compute(s,d,d,["RAN"]); assert False
    except ValueError as e: assert "Aucune heure restante" in str(e)
    dsf2={"id":"2","number":2,"label":"DSF 2","status":AFC_DSF_STATUS_CANCELLED,**r1}; s["afcDsfs"].append(dsf2)
    assert afc_dsf_next_number(s)==3
    dsf1["status"]=AFC_DSF_STATUS_CANCELLED
    assert afc_dsf_compute(s,d,d,["RAN"])["totalHours"]==14
    summary=afc_dsf_summary(s); assert summary["cards"][0]["remainingTotal"] >= 0
    snap=dsf2["students"][0]["modules"]["RAN"]; s["apsPlanningData"][0]["slots"][0]["durationMinutes"]=60
    assert dsf2["students"][0]["modules"]["RAN"] == snap

def test_period_without_hours_refused():
    s=sample_session()
    try: afc_dsf_compute(s,"2026-11-21","2026-11-22",["PAF"]); assert False
    except ValueError as e: assert "Aucune heure" in str(e)

def test_pdf_contains_students_labels_logo_and_no_nulls(tmp_path):
    from pypdf import PdfReader
    s=sample_session(); d=s["apsPlanningData"][0]["date"]; r=afc_dsf_compute(s,d,d,["RAN"])
    dsf={"id":"1","number":1,"label":"DSF 1","status":AFC_DSF_STATUS_FINALIZED,"createdAt":"2026-11-16 10:00:00",**r}
    out=tmp_path/"dsf.pdf"; generate_afc_dsf_pdf(s,dsf,str(out))
    text="\n".join(p.extract_text() or "" for p in PdfReader(str(out)).pages)
    assert "DUPONT Jean" in text and "MARTIN Sophie" in text
    assert "Remise à niveau (RAN)" in text and "Intégrale Academy" in text
    assert all(x not in text for x in ["None","null","undefined"])
