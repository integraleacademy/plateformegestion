from __future__ import annotations
from datetime import datetime, date

A3P_TOTAL_HOURS = 328
A3P_FORBIDDEN_TERMS = ("APS", "e-learning", "distanciel", "175h")
A3P_MODULES = [
    {"code":"UV1","title":"SST","hours":14,"locked":True},
    {"code":"UV2","title":"Module juridique","hours":22,"locked":False},
    {"code":"UV3","title":"Gestion des conflits","hours":14,"locked":False},
    {"code":"UV4","title":"Module stratégique","hours":8,"locked":False},
    {"code":"UV5","title":"Risques terroristes","hours":13,"locked":True},
    {"code":"UV6B","title":"Module professionnel approfondi hors déplacements","hours":113,"locked":False},
    {"code":"UV6A","title":"Déplacements et accompagnements","hours":45,"locked":True},
    {"code":"UV7","title":"Techniques professionnelles","hours":45,"locked":False},
    {"code":"UV8","title":"Gestion des risques","hours":40,"locked":False},
    {"code":"UV9","title":"Secourisme tactique d’urgence","hours":14,"locked":True},
]
A3P_AUTO_ORDER = [m["code"] for m in A3P_MODULES]
A3P_LOCKED_CODES = {m["code"] for m in A3P_MODULES if m["locked"]}
A3P_MODULE_BY_CODE = {m["code"]: m for m in A3P_MODULES}
assert sum(m["hours"] for m in A3P_MODULES) == A3P_TOTAL_HOURS

def _minutes(value: str) -> int:
    h, m = [int(x) for x in (value or "00:00").split(":")[:2]]
    return h * 60 + m

def _hhmm(total: int) -> str:
    return f"{total//60:02d}:{total%60:02d}"

def _slot_minutes(start: str, end: str) -> int:
    s, e = _minutes(start), _minutes(end)
    if e <= s:
        raise ValueError(f"Horaire invalide: {start}-{end}")
    return e - s

def _day_label(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][d.weekday()]

def a3p_empty_module_totals():
    return {m["code"]: 0 for m in A3P_MODULES}

def a3p_summary_from_planning(planning):
    totals = a3p_empty_module_totals(); total = 0; errors=[]
    for day in planning or []:
        last_end = None
        for slot in day.get("slots", []):
            code = slot.get("code")
            if code not in A3P_MODULE_BY_CODE: errors.append(f"Module inconnu: {code}"); continue
            start, end = slot.get("start"), slot.get("end")
            try: minutes = int(slot.get("durationMinutes") or _slot_minutes(start, end))
            except Exception as exc: errors.append(str(exc)); continue
            if last_end is not None and _minutes(start) < last_end: errors.append(f"Chevauchement le {day.get('date')}")
            last_end = _minutes(end)
            totals[code] += minutes; total += minutes
    rows = [{**m, "actualHours": round(totals[m["code"]]/60,2)} for m in A3P_MODULES]
    return {"totalHours": round(total/60,2), "moduleTotals": {k: round(v/60,2) for k,v in totals.items()}, "rows": rows, "errors": errors}

def validate_a3p_planning(planning, exam_date=None):
    summary = a3p_summary_from_planning(planning); errors=list(summary["errors"])
    if round(summary["totalHours"],2) != A3P_TOTAL_HOURS: errors.append(f"Le total A3P doit être exactement de {A3P_TOTAL_HOURS}h (actuel: {summary['totalHours']}h).")
    for m in A3P_MODULES:
        actual = round(summary["moduleTotals"].get(m["code"],0),2)
        if actual != m["hours"]: errors.append(f"{m['title']} doit totaliser {m['hours']}h (actuel: {actual}h).")
    if exam_date and any(d.get("date") == exam_date for d in planning or []): errors.append("La date d’examen ne doit pas être comptée dans les 328h.")
    return errors, summary

def generateA3pSchedule(config):
    days = config.get("days") or []
    locked = config.get("lockedModules") or {}
    trainer = ((config.get("trainerFirstName") or "") + " " + (config.get("trainerLastName") or "")).strip() or config.get("trainerName") or ""
    room = config.get("room") or "Salle à définir"
    planning=[]
    locked_totals = a3p_empty_module_totals()
    for day in days:
        if day.get("date") == config.get("examDate"): continue
        slots=[]
        for period in (("morningStart","morningEnd"),("afternoonStart","afternoonEnd")):
            start, end = day.get(period[0]), day.get(period[1])
            if bool(start) != bool(end):
                raise ValueError(f"Horaires incomplets pour le {day.get('date')}")
            if not start and not end:
                continue
            _slot_minutes(start,end)
            slots.append({"start":start,"end":end,"free":True})
        if not slots:
            raise ValueError(f"Aucun horaire renseigné pour le {day.get('date')}")
        for code, dates in locked.items():
            if day.get("date") in set(dates or []):
                for s in slots:
                    if s.get("free"):
                        s.update({"free":False,"code":code,"title":A3P_MODULE_BY_CODE[code]["title"],"locked":True,"trainer":trainer,"room":room,"durationMinutes":_slot_minutes(s["start"],s["end"])})
                        locked_totals[code]+=s["durationMinutes"]
        planning.append({"date":day.get("date"),"dayLabel":_day_label(day.get("date")),"slots":slots})
    unknown = set(locked) - set(A3P_MODULE_BY_CODE)
    if unknown:
        raise ValueError(f"Module inconnu: {', '.join(sorted(unknown))}")
    invalid_manual = sorted(set(locked) - A3P_LOCKED_CODES)
    if invalid_manual:
        labels = ", ".join(A3P_MODULE_BY_CODE[c]["title"] for c in invalid_manual)
        raise ValueError(f"Seuls les 4 modules imposés peuvent être verrouillés manuellement: {labels}")
    for code in A3P_LOCKED_CODES:
        expected=A3P_MODULE_BY_CODE[code]["hours"]*60
        if locked_totals[code] != expected:
            raise ValueError(f"Module manuel invalide: {A3P_MODULE_BY_CODE[code]['title']} = {locked_totals[code]/60:g}h / {expected/60:g}h")
    modules=[{"code":c,"remaining":A3P_MODULE_BY_CODE[c]["hours"]*60} for c in A3P_AUTO_ORDER if c not in A3P_LOCKED_CODES]
    idx=0
    for day in planning:
        new=[]
        for slot in day["slots"]:
            if not slot.get("free"):
                new.append(slot); continue
            cursor=_minutes(slot["start"]); endm=_minutes(slot["end"])
            while cursor < endm and idx < len(modules):
                take=min(endm-cursor, modules[idx]["remaining"]); code=modules[idx]["code"]
                new.append({"start":_hhmm(cursor),"end":_hhmm(cursor+take),"durationMinutes":take,"code":code,"title":A3P_MODULE_BY_CODE[code]["title"],"locked":False,"trainer":trainer,"room":room})
                cursor += take; modules[idx]["remaining"] -= take
                if modules[idx]["remaining"] == 0: idx += 1
            if cursor < endm: raise ValueError("Il y a plus d’heures disponibles que les 328h A3P à planifier.")
        day["slots"] = new
    if any(m["remaining"] for m in modules): raise ValueError("Le reste automatique ne peut pas être entièrement généré: heures insuffisantes.")
    errors, summary = validate_a3p_planning(planning, config.get("examDate"))
    if errors: raise ValueError(" ".join(errors))
    return {"planning": planning, "summary": summary}
