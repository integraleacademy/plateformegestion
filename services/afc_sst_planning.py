"""Regrouper le SST AFC sans déplacer les autres blocs ni changer les volumes."""

from copy import deepcopy
from datetime import date, timedelta


DAY_WINDOWS = ((510, 750), (810, 990))
TIME_FIELDS = {"start", "end", "duration", "durationMinutes"}
BLOCK_FIELDS = {"blockId", "blockType", "blockTotalMinutes", "is_atomic", "can_split", "required_same_date"}


def is_afc_sst_slot(slot):
    return slot.get("afcCategory") == "APS" and slot.get("uv") == "UV1"


def _minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _duration(slot):
    return int(slot.get("durationMinutes") or round(float(slot.get("duration") or 0) * 60))


def _hhmm(value):
    return f"{value // 60:02d}:{value % 60:02d}"


def _windows(slots):
    windows = []
    for slot in sorted(slots, key=lambda slot: slot["start"]):
        start, end = _minutes(slot["start"]), _minutes(slot["end"])
        if end <= start or end - start != _duration(slot):
            raise ValueError("Un créneau APS présente une durée incohérente.")
        if windows and start < windows[-1][1]:
            raise ValueError("Des créneaux APS se chevauchent.")
        if windows and start == windows[-1][1]:
            windows[-1] = (windows[-1][0], end)
        else:
            windows.append((start, end))
    return windows


def validate_afc_sst_days(planning):
    days = [day for day in planning or [] if any(is_afc_sst_slot(slot) for slot in day.get("slots", []))]
    errors = []
    if sum(_duration(slot) for day in days for slot in day["slots"] if is_afc_sst_slot(slot)) != 840:
        errors.append("Le SST (UV1) doit totaliser exactement 14h dans les 175h d’APS.")
    if len(days) != 2 or any(sum(_duration(slot) for slot in day["slots"] if is_afc_sst_slot(slot)) != 420 for day in days):
        errors.append("Le SST (UV1) doit être regroupé sur exactement deux journées de 7h.")
    for day in days:
        if any(not is_afc_sst_slot(slot) for slot in day["slots"]):
            errors.append(f"La journée SST du {day['date']} doit être entièrement consacrée au SST, sans autre activité.")
    return errors


def group_afc_sst_days(planning):
    """Réserver deux jours complets consécutifs et redistribuer uniquement l’APS concerné.

    Les fenêtres horaires restent identiques, de même que le programme, les
    affectations et les notes. Le SP, la PAF et toutes les autres catégories
    restent strictement inchangés. Aucun volume manquant n’est inventé.
    """
    corrected = deepcopy(planning)
    if not validate_afc_sst_days(corrected):
        return corrected
    sst_days = [day["date"] for day in corrected if any(is_afc_sst_slot(slot) for slot in day.get("slots", []))]
    sst_total = sum(_duration(slot) for day in corrected for slot in day.get("slots", []) if is_afc_sst_slot(slot))
    if sst_total != 840:
        raise ValueError("Impossible de regrouper le SST : le planning enregistré doit déjà contenir exactement 14h de SST.")
    by_date = {day["date"]: day for day in corrected}
    if len(by_date) != len(corrected):
        raise ValueError("Le planning contient plusieurs entrées pour une même date.")
    complete_dates = set()
    for iso, day in by_date.items():
        slots = day.get("slots", [])
        if slots and all(slot.get("afcCategory") == "APS" for slot in slots) and _windows(slots) == list(DAY_WINDOWS):
            complete_dates.add(iso)
    targets = None
    for iso in sorted(complete_dates):
        next_iso = (date.fromisoformat(iso) + timedelta(days=1)).isoformat()
        if iso >= min(sst_days) and next_iso in complete_dates:
            targets = {iso, next_iso}
            break
    if targets is None:
        raise ValueError("Deux journées APS consécutives de 7h, sans SP ni PAF, sont nécessaires pour placer le SST.")

    start_date, end_date = min(sst_days), max(max(sst_days), max(targets))
    streams = {True: [], False: []}
    windows = []
    for iso in sorted(by_date):
        if not start_date <= iso <= end_date:
            continue
        slots = sorted((slot for slot in by_date[iso]["slots"] if slot.get("afcCategory") == "APS"), key=lambda slot: slot["start"])
        windows.extend((iso, start, end) for start, end in _windows(slots))
        for slot in slots:
            sst = is_afc_sst_slot(slot)
            ignored = TIME_FIELDS | (BLOCK_FIELDS if sst else set())
            content = {key: deepcopy(value) for key, value in slot.items() if key not in ignored}
            stream = streams[sst]
            if stream and stream[-1][0] == content:
                stream[-1][1] += _duration(slot)
            else:
                stream.append([content, _duration(slot)])
    for sst in (True, False):
        capacity = sum(end - start for iso, start, end in windows if (iso in targets) == sst)
        if capacity != sum(minutes for _, minutes in streams[sst]):
            raise ValueError("Le regroupement SST modifierait les volumes enregistrés.")
    for iso in by_date:
        if start_date <= iso <= end_date:
            by_date[iso]["slots"] = [slot for slot in by_date[iso]["slots"] if slot.get("afcCategory") != "APS"]
    indexes = {True: 0, False: 0}
    for iso, start, end in windows:
        sst = iso in targets
        while start < end:
            content, remaining = streams[sst][indexes[sst]]
            duration = min(end - start, remaining)
            slot = deepcopy(content)
            slot.update(start=_hhmm(start), end=_hhmm(start + duration), durationMinutes=duration, duration=round(duration / 60, 2))
            if sst:
                slot.update(blockId=f"SST-{iso}", blockType="SST", blockTotalMinutes=420, is_atomic=True, can_split=False, required_same_date=True)
            by_date[iso]["slots"].append(slot)
            streams[sst][indexes[sst]][1] -= duration
            start += duration
            if not streams[sst][indexes[sst]][1]:
                indexes[sst] += 1
    for iso, day in by_date.items():
        if start_date <= iso <= end_date:
            day["slots"].sort(key=lambda slot: slot["start"])
    errors = validate_afc_sst_days(corrected)
    if errors:
        raise ValueError(" ".join(errors))
    return corrected
