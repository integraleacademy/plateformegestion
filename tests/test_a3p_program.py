import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from a3p_program import generateA3pSchedule, validate_a3p_planning, A3P_FORBIDDEN_TERMS

def days(n=48):
    import datetime as dt
    d=dt.date(2026,1,5); out=[]
    while len(out)<n:
        if d.weekday()<5:
            out.append({"date":d.isoformat(),"dayStart":"08:30","dayEnd":"16:30"})
        d += dt.timedelta(days=1)
    out[-1]["dayStart"]="10:00"
    out[-1]["dayEnd"]="15:00"
    return out

def config():
    ds=days(48)
    ds[3]["dayStart"]="13:00"
    ds[3]["dayEnd"]="20:00"
    ds[10]["dayEnd"]="12:30"
    return {"trainerFirstName":"Jean","trainerLastName":"Dupont","room":"Salle 1","examDate":"2026-04-30","days":ds,
            "lockedModules":{"UV1":[ds[0]["date"],ds[1]["date"]],"UV5":[ds[2]["date"],ds[3]["date"]],"UV6A":[d["date"] for d in ds[4:11]],"UV9":[ds[11]["date"],ds[12]["date"]]}}

def test_a3p_schedule_totals_and_locked_modules():
    result=generateA3pSchedule(config()); s=result["summary"]
    assert s["totalHours"] == 328
    assert s["moduleTotals"]["UV1"] == 14
    assert s["moduleTotals"]["UV5"] == 13
    assert s["moduleTotals"]["UV6A"] == 45
    assert s["moduleTotals"]["UV9"] == 14
    assert s["moduleTotals"]["UV2"] == 22
    assert not validate_a3p_planning(result["planning"], config()["examDate"])[0]

def test_a3p_rejects_bad_total_and_bad_locked_module():
    bad=config(); bad["days"]=bad["days"][:-1]
    with pytest.raises(ValueError): generateA3pSchedule(bad)
    bad=config(); bad["lockedModules"]["UV1"]=[bad["days"][0]["date"]]
    with pytest.raises(ValueError): generateA3pSchedule(bad)

def test_a3p_forbidden_terms_not_in_program_constants():
    import a3p_program
    text="\n".join(str(v) for k,v in vars(a3p_program).items() if k.startswith("A3P_") and k != "A3P_FORBIDDEN_TERMS")
    assert not any(term in text for term in A3P_FORBIDDEN_TERMS)


def test_a3p_day_start_end_split_examples_and_errors():
    from a3p_program import _day_training_slots
    assert _day_training_slots({"date":"2026-01-01","dayStart":"13:00","dayEnd":"20:00"}) == [("13:00", "16:00"), ("17:00", "20:00")]
    assert _day_training_slots({"date":"2026-01-02","dayStart":"08:30","dayEnd":"16:30"}) == [("08:30", "12:00"), ("13:00", "16:30")]
    with pytest.raises(ValueError, match="fin est avant"):
        _day_training_slots({"date":"2026-01-03","dayStart":"12:00","dayEnd":"11:00"})
    with pytest.raises(ValueError, match="au moins 2h"):
        _day_training_slots({"date":"2026-01-04","dayStart":"10:00","dayEnd":"11:30"})
