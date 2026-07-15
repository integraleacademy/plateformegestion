from __future__ import annotations
from datetime import date, datetime, timedelta, time as dt_time

DESP_CODE = "DESP"
DESP_LABEL = "Dirigeant d’une société de sécurité privée (DESP)"
DESP_ELEARNING_HOURS = 174
DESP_PRESENTIEL_HOURS = 70
DESP_TOTAL_HOURS = 244
DESP_ELEARNING_MAX_DAILY_MINUTES = 7 * 60
DESP_PRESENTIEL_MAX_DAILY_MINUTES = 8 * 60
DESP_MAX_DAILY_MINUTES = DESP_PRESENTIEL_MAX_DAILY_MINUTES
DESP_MORNING_MINUTES = 4 * 60
DESP_AFTERNOON_START = dt_time(13, 30)

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

def is_desp_training_day(day: date, exam_iso: str = "", allow_saturday: bool = False) -> bool:
    max_weekday = 5 if allow_saturday else 4
    return day.isoformat() != exam_iso and day.weekday() <= max_weekday and day not in french_public_holidays(day.year)

def desp_working_days_between(start: date, end: date, exam_iso: str = "", allow_saturday: bool = False):
    days=[]; cur=start
    while cur <= end:
        if is_desp_training_day(cur, exam_iso, allow_saturday): days.append(cur)
        cur += timedelta(days=1)
    return days

def _hhmm(t): return t.strftime("%H:%M")
def _add(t, minutes): return (datetime.combine(date(2000,1,1), t) + timedelta(minutes=minutes)).time()

def _period_capacity_message(label, start, end, required_minutes, max_daily_minutes, exam_iso="", allow_saturday=False):
    days = desp_working_days_between(start, end, exam_iso, allow_saturday)
    capacity_hours = len(days) * max_daily_minutes // 60
    return (f"Impossible de générer le planning {label} : {required_minutes // 60} heures à placer, "
            f"{len(days)} journées disponibles, capacité maximale {capacity_hours}h "
            f"à {max_daily_minutes // 60}h/jour entre le {start.strftime('%d/%m/%Y')} "
            f"et le {end.strftime('%d/%m/%Y')}. Modifiez les dates ou autorisez une journée supplémentaire.")

def _daily_minutes_for_period(days_count: int, required_minutes: int, max_daily_minutes: int) -> list[int]:
    if days_count * max_daily_minutes < required_minutes:
        return []
    if max_daily_minutes == DESP_ELEARNING_MAX_DAILY_MINUTES:
        full_days, remainder = divmod(required_minutes, max_daily_minutes)
        values = [max_daily_minutes] * full_days
        if remainder:
            values.append(remainder)
        return values if len(values) <= days_count else []

    required_hours, leftover_minutes = divmod(required_minutes, 60)
    if leftover_minutes:
        return []
    for six_hour_days in range(0, days_count + 1):
        remaining_days_after_sixes = days_count - six_hour_days
        remaining_hours_after_sixes = required_hours - (six_hour_days * 6)
        if remaining_hours_after_sixes < 0:
            continue
        for eight_hour_days in range(remaining_days_after_sixes, -1, -1):
            seven_hour_days = remaining_days_after_sixes - eight_hour_days
            if (eight_hour_days * 8) + (seven_hour_days * 7) == remaining_hours_after_sixes:
                return ([8 * 60] * eight_hour_days) + ([7 * 60] * seven_hour_days) + ([6 * 60] * six_hour_days)
    return []

def generate_desp_planning(elearning_start: date, elearning_end: date, presentiel_start: date, presentiel_end: date, trainer="", room="", exam_iso="", allow_saturday: bool = False):
    if presentiel_start <= elearning_end:
        raise ValueError("La période présentielle DESP doit commencer après la fin complète du distanciel.")
    planning=[]
    for modality, start, end, required, part_label, trainer_for_slot, room_for_slot in (
        ("elearning", elearning_start, elearning_end, DESP_ELEARNING_HOURS*60, "PÉRIODE 1 — E-LEARNING / DISTANCIEL — 174h", "", ""),
        ("presentiel", presentiel_start, presentiel_end, DESP_PRESENTIEL_HOURS*60, "PÉRIODE 2 — PRÉSENTIEL AU CENTRE — 70h", trainer, room),
    ):
        days = desp_working_days_between(start, end, exam_iso, allow_saturday if modality == "presentiel" else False)
        if not days:
            raise ValueError(f"Impossible de générer le planning DESP : aucune journée ouvrée disponible pour {('le distanciel' if modality == 'elearning' else 'le présentiel')} entre le {start.strftime('%d/%m/%Y')} et le {end.strftime('%d/%m/%Y')}.")
        max_daily_minutes = DESP_ELEARNING_MAX_DAILY_MINUTES if modality == "elearning" else DESP_PRESENTIEL_MAX_DAILY_MINUTES
        if len(days) * max_daily_minutes < required:
            raise ValueError(_period_capacity_message("distanciel" if modality == "elearning" else "présentiel", start, end, required, max_daily_minutes, exam_iso, allow_saturday if modality == "presentiel" else False))
        seqs = [dict(s, remainingMinutes=s["durationMinutes"]) for s in desp_sequences(modality)]
        idx=0; remaining_total=required
        daily_minutes = _daily_minutes_for_period(len(days), required, max_daily_minutes)
        for day, target_minutes in zip(days, daily_minutes):
            if remaining_total <= 0: break
            slots=[]
            morning_minutes = min(DESP_MORNING_MINUTES, target_minutes)
            afternoon_minutes = max(0, target_minutes - morning_minutes)
            for slot_start, slot_minutes in ((dt_time(8,30), morning_minutes), (DESP_AFTERNOON_START, afternoon_minutes)):
                if slot_minutes <= 0:
                    continue
                cursor=slot_start; remaining_slot=min(slot_minutes, remaining_total)
                while remaining_slot > 0 and idx < len(seqs):
                    seq=seqs[idx]; take=min(remaining_slot, seq["remainingMinutes"]); end_time=_add(cursor, take)
                    slots.append({"start": _hhmm(cursor), "end": _hhmm(end_time), "duration": take // 60 if take % 60 == 0 else take / 60, "durationMinutes": take, "uv": seq["code"], "theme": seq["theme"], "title": seq["title"], "part": part_label, "room": room_for_slot, "trainer": trainer_for_slot, "modality": modality})
                    seq["remainingMinutes"] -= take; remaining_slot -= take; remaining_total -= take; cursor = end_time
                    if seq["remainingMinutes"] == 0: idx += 1
                if remaining_total <= 0 or idx >= len(seqs): break
            if slots:
                label = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][day.weekday()]
                planning.append({"date": day.isoformat(), "dayLabel": f"{label} {day.strftime('%d/%m/%Y')}", "slots": slots})
        if remaining_total != 0:
            raise ValueError(_period_capacity_message("distanciel" if modality == "elearning" else "présentiel", start, end, required, max_daily_minutes, exam_iso, allow_saturday if modality == "presentiel" else False))
    return planning

def desp_summary_rows():
    return [
        {
            "uv": row["code"],
            "label": f"{('Distanciel' if row['modality'] == 'elearning' else 'Présentiel')} — {row['theme']} — {row['title']}",
            "hours": row["hours"],
            "modality": row["modality"],
        }
        for row in desp_sequences()
    ]

def desp_summary_from_planning(planning):
    minute_totals={"elearning":0,"presentiel":0}; total_minutes=0; errors=[]; warnings=[]
    seen_presentiel=False
    for day in planning or []:
        try: d=datetime.strptime(day.get("date"), "%Y-%m-%d").date()
        except Exception: errors.append(f"Date invalide: {day.get('date')}"); continue
        if not is_desp_training_day(d, allow_saturday=True): errors.append(f"La journée du {day.get('date')} est un jour non travaillé.")
        day_minutes=0
        for slot in day.get("slots", []):
            modality=slot.get("modality") or "presentiel"
            if modality == "presentiel": seen_presentiel=True
            if modality == "elearning" and seen_presentiel: errors.append("Une séquence distancielle est positionnée après le début du présentiel.")
            mins=int(slot.get("durationMinutes") or 0); day_minutes += mins; minute_totals[modality]=minute_totals.get(modality,0)+mins; total_minutes += mins
        max_daily_minutes = DESP_PRESENTIEL_MAX_DAILY_MINUTES if any((slot.get("modality") or "presentiel") == "presentiel" for slot in day.get("slots", [])) else DESP_ELEARNING_MAX_DAILY_MINUTES
        if day_minutes > max_daily_minutes: errors.append(f"La journée du {day.get('date')} dépasse {max_daily_minutes//60}h de formation ({day_minutes//60}h).")
    totals={k: round(v/60,2) for k,v in minute_totals.items()}
    total=round(total_minutes/60,2)
    if minute_totals["elearning"] != DESP_ELEARNING_HOURS*60: errors.append(f"Le total distanciel doit être exactement de 174h (actuel: {totals['elearning']:g}h).")
    if minute_totals["presentiel"] != DESP_PRESENTIEL_HOURS*60: errors.append(f"Le total présentiel doit être exactement de 70h (actuel: {totals['presentiel']:g}h).")
    if total_minutes != DESP_TOTAL_HOURS*60: errors.append(f"Le total DESP doit être exactement de 244h (actuel: {total:g}h).")
    rows = desp_summary_rows()
    return {"total_hours": total, "uv_totals": {row["uv"]: row["hours"] for row in rows}, "uv_rows": rows, "modality_totals": totals, "errors": errors, "warnings": warnings, "days_count": len(planning or []), "slots_count": sum(len(d.get('slots', [])) for d in planning or [])}
