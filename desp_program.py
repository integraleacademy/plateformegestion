from __future__ import annotations
from datetime import date, datetime, timedelta, time as dt_time

DESP_CODE = "DESP"
DESP_LABEL = "Dirigeant d’entreprise de sécurité privée (DESP)"
DESP_ELEARNING_HOURS = 174
DESP_PRESENTIEL_HOURS = 70
DESP_TOTAL_HOURS = 244
DESP_MAX_DAILY_MINUTES = 7 * 60

DESP_SEQUENCES = [
    # Distanciel — 174h
    ("elearning", "Modules juridiques — Droit du travail", "Connaître les règles d’embauchage et de rupture du contrat de travail", 8),
    ("elearning", "Modules juridiques — Droit du travail", "Connaître les conditions de conclusion du contrat de travail", 4),
    ("elearning", "Modules juridiques — Droit du travail", "Connaître les infractions en matière de droit du travail", 4),
    ("elearning", "Modules juridiques — Droit du travail", "Connaître la réglementation des conditions de travail", 4),
    ("elearning", "Modules juridiques — Droit du travail", "Connaître les règles de représentation du personnel", 4),
    ("elearning", "Modules juridiques — Droit du travail", "Connaître la réglementation en matière d’hygiène et de sécurité", 4),
    ("elearning", "Modules juridiques — Droit du travail", "Connaître les acteurs institutionnels", 4),
    ("elearning", "Modules juridiques — Droit du travail", "Connaître la réglementation applicable aux rapports collectifs du travail et la responsabilité du chef d’entreprise", 4),
    ("elearning", "Modules juridiques — Droit du travail", "Rupture du contrat et accident du travail notamment", 4),
    ("elearning", "Modules juridiques — Environnement juridique de la sécurité privée", "Connaître le livre VI du Code de la sécurité intérieure", 12),
    ("elearning", "Modules juridiques — Environnement juridique de la sécurité privée", "Connaître les dispositions utiles du Code pénal", 12),
    ("elearning", "Modules juridiques — Environnement juridique de la sécurité privée", "Maîtriser les garanties liées au respect des libertés publiques", 4),
    ("elearning", "Modules juridiques — Environnement juridique de la sécurité privée", "Maîtriser les aspects législatifs et juridiques intéressant la sécurité privée", 4),
    ("elearning", "Modules juridiques — Environnement juridique de la sécurité privée", "Respecter la déontologie professionnelle", 4),
    ("elearning", "Modules juridiques — Environnement juridique de la sécurité privée", "Maîtriser l’environnement institutionnel", 4),
    ("elearning", "Modules juridiques — Environnement juridique de la sécurité privée", "Maîtriser la réglementation relative à l’acquisition, la détention, l’importation, le transport et la conservation des armes", 4),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Connaître les modalités de création d’entreprise", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Connaître les modalités de reprise et de rachat d’entreprise", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Connaître les moyens à mettre en œuvre pour mener à bien le projet", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Analyser les risques", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Étudier la stratégie commerciale et marketing", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Examiner les approches juridiques", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Examiner les approches financières", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Étudier le seuil de rentabilité", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Connaître les aides et la prévoyance", 6),
    ("elearning", "Gestion administrative et financière — Management de l’entreprise et des moyens", "Maîtriser la communication d’entreprise", 6),
    ("elearning", "Connaissances des marchés — Appels d’offres", "Connaissance des donneurs d’ordre publics et droit des contrats administratifs", 5),
    ("elearning", "Connaissances des marchés — Appels d’offres", "Connaissance des donneurs d’ordre privés et droit des contrats privés", 5),
    ("elearning", "Connaissances des marchés — Appels d’offres", "Trouver un appel d’offres", 5),
    ("elearning", "Connaissances des marchés — Appels d’offres", "Analyser d’un point de vue théorique un appel d’offres", 5),
    ("elearning", "Connaissances des marchés — Appels d’offres", "Savoir gérer la relation clientèle", 5),
    ("elearning", "Connaissances des marchés — Appels d’offres", "Gérer la rupture de contrat", 5),
    # Présentiel — 70h
    ("presentiel", "Connaissances stratégiques", "Connaître le positionnement de la sécurité privée dans l’architecture globale de sécurité", 8),
    ("presentiel", "Connaissances stratégiques", "Connaître le rôle de la police municipale", 4),
    ("presentiel", "Connaissances stratégiques", "Connaissance des phénomènes criminels", 4),
    ("presentiel", "Connaissances stratégiques", "Organisation du secteur de la sécurité privée", 4),
    ("presentiel", "Connaissances stratégiques", "Spécificités par branche", 4),
    ("presentiel", "Connaissances stratégiques", "Informations relatives aux métiers de la sécurité incendie", 4),
    ("presentiel", "Connaissances stratégiques", "Formation universitaire et professionnelle en matière de sécurité", 4),
    ("presentiel", "Connaissances stratégiques", "Évolution et prospective de la sécurité privée", 4),
    ("presentiel", "Connaissances stratégiques", "Environnement européen et international", 4),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Connaître les consignes et procédures d’exploitation et les mains courantes", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Connaître les équipements de communication interne fixes, mobiles et embarqués", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Équipements de protection individuelle", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Rondes de surveillance et systèmes de contrôle de rondes", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Équipements de protection mécanique périphérique et périmétrique", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Équipements de protection électronique périphérique, périmétrique et volumétrique et systèmes d’alarmes", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Systèmes de contrôle d’accès", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Systèmes de vidéosurveillance, de télésurveillance et intervention sur alarme", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Équipements de sécurité incendie", 2),
    ("presentiel", "Connaissances pratiques — Équipements et techniques", "Évacuations", 2),
    ("presentiel", "Connaissances des marchés — Appels d’offres", "Réceptionner et répondre d’un point de vue pratique à un appel d’offres", 5),
    ("presentiel", "Connaissances des marchés — Appels d’offres", "Gestion de projet", 5),
]

def desp_sequences(modality=None):
    rows = []
    counters = {"elearning": 0, "presentiel": 0}
    for seq_modality, theme, title, hours in DESP_SEQUENCES:
        counters[seq_modality] += 1
        if modality and seq_modality != modality:
            continue
        rows.append({"modality": seq_modality, "code": f"DESP-{seq_modality[:1].upper()}{counters[seq_modality]:02d}", "theme": theme, "title": title, "hours": hours, "durationMinutes": int(hours * 60)})
    return rows

def desp_program_totals():
    elearning = sum(s[3] for s in DESP_SEQUENCES if s[0] == "elearning")
    presentiel = sum(s[3] for s in DESP_SEQUENCES if s[0] == "presentiel")
    return {"elearning": elearning, "presentiel": presentiel, "total": elearning + presentiel}

assert desp_program_totals() == {"elearning": DESP_ELEARNING_HOURS, "presentiel": DESP_PRESENTIEL_HOURS, "total": DESP_TOTAL_HOURS}

def _easter_date(year: int) -> date:
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3; h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31; day=((h+l-7*m+114)%31)+1
    return date(year, month, day)

def french_public_holidays(year: int) -> set[date]:
    easter = _easter_date(year)
    return {date(year,1,1), date(year,5,1), date(year,5,8), date(year,7,14), date(year,8,15), date(year,11,1), date(year,11,11), date(year,12,25), easter + timedelta(days=1), easter + timedelta(days=39), easter + timedelta(days=50)}

def is_desp_training_day(day: date, exam_iso: str = "") -> bool:
    return day.isoformat() != exam_iso and day.weekday() < 5 and day not in french_public_holidays(day.year)

def desp_working_days_between(start: date, end: date, exam_iso: str = ""):
    days=[]; cur=start
    while cur <= end:
        if is_desp_training_day(cur, exam_iso): days.append(cur)
        cur += timedelta(days=1)
    return days

def _hhmm(t): return t.strftime("%H:%M")
def _add(t, minutes): return (datetime.combine(date(2000,1,1), t) + timedelta(minutes=minutes)).time()

def _period_error(label, start, end, required_minutes, exam_iso=""):
    days = desp_working_days_between(start, end, exam_iso)
    available = len(days) * DESP_MAX_DAILY_MINUTES
    return (f"Impossible de générer le planning DESP : {label} nécessite {required_minutes/60:g}h, "
            f"mais la période du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')} ne permet que {available/60:g}h. "
            "Corrigez les dates de distanciel/présentiel de la session.")

def generate_desp_planning(elearning_start: date, elearning_end: date, presentiel_start: date, presentiel_end: date, trainer="", room="", exam_iso=""):
    if presentiel_start <= elearning_end:
        raise ValueError("La période présentielle DESP doit commencer après la fin complète du distanciel.")
    planning=[]
    for modality, start, end, required, part_label, trainer_for_slot, room_for_slot in (
        ("elearning", elearning_start, elearning_end, DESP_ELEARNING_HOURS*60, "PÉRIODE 1 — E-LEARNING / DISTANCIEL — 174h", "", ""),
        ("presentiel", presentiel_start, presentiel_end, DESP_PRESENTIEL_HOURS*60, "PÉRIODE 2 — PRÉSENTIEL AU CENTRE — 70h", trainer, room),
    ):
        days = desp_working_days_between(start, end, exam_iso)
        if len(days) * DESP_MAX_DAILY_MINUTES < required:
            raise ValueError(_period_error("le distanciel" if modality == "elearning" else "le présentiel", start, end, required, exam_iso))
        seqs = [dict(s, remainingMinutes=s["durationMinutes"]) for s in desp_sequences(modality)]
        idx=0; remaining_total=required
        for day in days:
            if remaining_total <= 0: break
            slots=[]
            for slot_start, slot_minutes in ((dt_time(8,30), 240), (dt_time(13,30), 180)):
                cursor=slot_start; remaining_slot=min(slot_minutes, remaining_total)
                while remaining_slot > 0 and idx < len(seqs):
                    seq=seqs[idx]; take=min(remaining_slot, seq["remainingMinutes"]); end_time=_add(cursor, take)
                    slots.append({"start": _hhmm(cursor), "end": _hhmm(end_time), "duration": round(take/60,2), "durationMinutes": take, "uv": seq["code"], "theme": seq["theme"], "title": seq["title"], "part": part_label, "room": room_for_slot, "trainer": trainer_for_slot, "modality": modality})
                    seq["remainingMinutes"] -= take; remaining_slot -= take; remaining_total -= take; cursor = end_time
                    if seq["remainingMinutes"] == 0: idx += 1
                if remaining_total <= 0 or idx >= len(seqs): break
            if slots:
                label = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][day.weekday()]
                planning.append({"date": day.isoformat(), "dayLabel": f"{label} {day.strftime('%d/%m/%Y')}", "slots": slots})
        if remaining_total != 0:
            raise ValueError(_period_error("le distanciel" if modality == "elearning" else "le présentiel", start, end, required, exam_iso))
    return planning

def desp_summary_from_planning(planning):
    totals={"elearning":0.0,"presentiel":0.0}; total=0.0; errors=[]
    seen_presentiel=False
    for day in planning or []:
        try: d=datetime.strptime(day.get("date"), "%Y-%m-%d").date()
        except Exception: errors.append(f"Date invalide: {day.get('date')}"); continue
        if not is_desp_training_day(d): errors.append(f"La journée du {day.get('date')} est un jour non travaillé.")
        day_minutes=0
        for slot in day.get("slots", []):
            modality=slot.get("modality") or "presentiel"
            if modality == "presentiel": seen_presentiel=True
            if modality == "elearning" and seen_presentiel: errors.append("Une séquence distancielle est positionnée après le début du présentiel.")
            mins=int(slot.get("durationMinutes") or 0); day_minutes += mins; totals[modality]=round(totals.get(modality,0)+mins/60,2); total=round(total+mins/60,2)
        if day_minutes > DESP_MAX_DAILY_MINUTES: errors.append(f"La journée du {day.get('date')} dépasse 7h de formation.")
    if totals["elearning"] != DESP_ELEARNING_HOURS: errors.append(f"Le total distanciel doit être exactement de 174h (actuel: {totals['elearning']:g}h).")
    if totals["presentiel"] != DESP_PRESENTIEL_HOURS: errors.append(f"Le total présentiel doit être exactement de 70h (actuel: {totals['presentiel']:g}h).")
    if total != DESP_TOTAL_HOURS: errors.append(f"Le total DESP doit être exactement de 244h (actuel: {total:g}h).")
    return {"total_hours": total, "modality_totals": totals, "errors": errors, "days_count": len(planning or []), "slots_count": sum(len(d.get('slots', [])) for d in planning or [])}
