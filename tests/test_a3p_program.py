import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from a3p_program import generateA3pSchedule, validate_a3p_planning, A3P_FORBIDDEN_TERMS

def days(n=47):
    import datetime as dt
    d=dt.date(2026,1,5); out=[]
    while len(out)<n:
        if d.weekday()<5: out.append({"date":d.isoformat(),"morningStart":"08:30","morningEnd":"12:30","afternoonStart":"13:30","afternoonEnd":"16:30"})
        d += dt.timedelta(days=1)
    out[-1]["afternoonEnd"]="14:30" # 326? 46*7+5=327? Actually 46*7 +5 =327
    return out

def config():
    ds=days(48)
    ds[3]["afternoonEnd"]="15:30"
    ds[10]["morningEnd"]="11:30"
    ds[10]["afternoonStart"]=""
    ds[10]["afternoonEnd"]=""
    ds[-1]["morningEnd"]="12:30"
    ds[-1]["afternoonStart"]=""
    ds[-1]["afternoonEnd"]=""
    return {"trainerFirstName":"Jean","trainerLastName":"Dupont","room":"Salle 1","examDate":"2026-03-12","days":ds,
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

def test_a3p_accepts_locked_half_day_slots_with_adjusted_last_slot():
    import datetime as dt
    ds=[]; d=dt.date(2026,6,8)
    for i in range(47):
        ds.append({"date":(d+dt.timedelta(days=i)).isoformat(),"morningStart":"09:00","morningEnd":"12:30","afternoonStart":"13:30","afternoonEnd":"17:00"})
    ds[-1]["afternoonEnd"]="16:00"
    locked={"UV1":[],"UV5":[],"UV6A":[],"UV9":[]}
    def add(code, index, period, hours=3.5):
        start = "09:00" if period == "morning" else "13:30"
        end_minutes = (9 * 60 if period == "morning" else 13 * 60 + 30) + int(hours * 60)
        locked[code].append({"date":ds[index]["date"],"period":period,"startTime":start,"endTime":f"{end_minutes//60:02d}:{end_minutes%60:02d}","hours":hours,"moduleId":code})
    for index in (0, 1):
        add("UV1", index, "morning"); add("UV1", index, "afternoon")
    add("UV5", 2, "morning"); add("UV5", 2, "afternoon"); add("UV5", 3, "morning"); add("UV5", 3, "afternoon", 2.5)
    remaining = 45; index = 4
    while remaining > 0:
        for period in ("morning", "afternoon"):
            if remaining <= 0: break
            take = min(3.5, remaining); add("UV6A", index, period, take); remaining -= take
        index += 1
    for period_index in range(4):
        add("UV9", index + period_index // 2, "morning" if period_index % 2 == 0 else "afternoon")

    result = generateA3pSchedule({"trainerFirstName":"Jean","trainerLastName":"Dupont","room":"Salle 1","days":ds,"lockedModules":locked})

    assert result["summary"]["totalHours"] == 328
    assert result["summary"]["moduleTotals"]["UV5"] == 13
    assert any(slot["end"] == "16:00" and slot["free"] is False for day in result["planning"] for slot in day["slots"] if slot.get("code") == "UV5")
