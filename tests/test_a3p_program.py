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
    ds[10]["dayEnd"]="12:30"
    out_last = ds[-1]
    out_last["dayStart"]="10:00"
    out_last["dayEnd"]="14:00"
    return {"trainerFirstName":"Jean","trainerLastName":"Dupont","room":"Salle 1","examDate":"2026-04-30","days":ds,
            "lockedModules":{"UV1":[ds[0]["date"],ds[1]["date"]],"UV5":[{"date":ds[2]["date"],"start":"08:30","end":"12:00","durationMinutes":210},{"date":ds[2]["date"],"start":"13:00","end":"16:30","durationMinutes":210},{"date":ds[3]["date"],"start":"08:30","end":"12:00","durationMinutes":210},{"date":ds[3]["date"],"start":"13:00","end":"15:30","durationMinutes":150}],"UV6A":[d["date"] for d in ds[4:11]],"UV9":[ds[11]["date"],ds[12]["date"]]}}

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


def tiny_config(locked_modules, extra_days=45):
    ds = days(extra_days)
    return {"trainerFirstName":"Jean","trainerLastName":"Dupont","room":"Salle 1","examDate":"2026-04-30","days":ds,"lockedModules":locked_modules}

def test_a3p_partial_locked_module_13h_leaves_one_hour_reusable():
    cfg = config()
    result = generateA3pSchedule(cfg)
    uv5 = [slot for day in result["planning"] for slot in day["slots"] if slot["code"] == "UV5"]
    assert sum(slot["durationMinutes"] for slot in uv5) == 780
    assert uv5[-1]["start"] == "13:00"
    assert uv5[-1]["end"] == "15:30"
    same_day = next(day for day in result["planning"] if day["date"] == cfg["days"][3]["date"])
    assert any(slot["start"] == "15:30" and slot["end"] == "16:30" and slot["code"] == "UV2" for slot in same_day["slots"])

def test_a3p_rejects_overlapping_precise_locked_slots():
    cfg = config()
    cfg["lockedModules"]["UV1"] = [
        {"date": cfg["days"][0]["date"], "start":"08:30", "end":"12:00", "durationMinutes":210},
        {"date": cfg["days"][0]["date"], "start":"11:00", "end":"14:30", "durationMinutes":210},
        {"date": cfg["days"][1]["date"], "start":"08:30", "end":"12:00", "durationMinutes":210},
        {"date": cfg["days"][1]["date"], "start":"13:00", "end":"16:30", "durationMinutes":210},
    ]
    with pytest.raises(ValueError, match="Chevauchement"):
        generateA3pSchedule(cfg)

def test_a3p_legacy_full_day_locked_dates_still_supported():
    cfg = config()
    cfg["lockedModules"]["UV5"] = [cfg["days"][2]["date"], cfg["days"][3]["date"]]
    with pytest.raises(ValueError, match="Risques terroristes = 14h / 13h"):
        generateA3pSchedule(cfg)
