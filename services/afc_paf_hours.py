"""Porter la PAF à 21 h tout en conservant ses quatre dates et l’ordre des cours."""

from copy import deepcopy


def _duration(slot):
    return int(slot.get("durationMinutes") or round(float(slot.get("duration") or 0) * 60))


def _minute(value):
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def _hhmm(value):
    return f"{value // 60:02d}:{value % 60:02d}"


def _windows(slots):
    windows = []
    for slot in sorted(slots, key=lambda item: item["start"]):
        start, end = _minute(slot["start"]), _minute(slot["end"])
        if end - start != _duration(slot) or end <= start:
            raise ValueError("Un créneau APS présente une durée incohérente.")
        if windows and start < windows[-1][1]:
            raise ValueError("Des créneaux APS se chevauchent.")
        if windows and start == windows[-1][1]:
            windows[-1] = (windows[-1][0], end)
        else:
            windows.append((start, end))
    return windows


def correct_afc_paf_hours(planning):
    corrected = deepcopy(planning)
    total = sum(_duration(slot) for day in corrected for slot in day.get("slots", []) if slot.get("afcCategory") == "PAF")
    if total == 21 * 60:
        return corrected
    if total != 20 * 60:
        raise ValueError("La correction PAF attend un ancien volume de 20h ou un volume déjà corrigé de 21h.")
    by_date = {day["date"]: day for day in corrected}
    if len(by_date) != len(corrected):
        raise ValueError("Le planning contient plusieurs entrées pour une même date.")
    first, last = "2027-01-06", "2027-01-14"
    source, target = by_date.get(first, {}), by_date.get(last, {})
    source_slots, target_slots = source.get("slots", []), target.get("slots", [])
    if not source_slots or any(slot.get("afcCategory") != "APS" for slot in source_slots) or _windows(source_slots) != [(510, 750), (810, 930)]:
        raise ValueError("Le 06/01 doit contenir 6h d’APS et laisser libre le créneau 15h30–16h30.")
    paf = sorted((slot for slot in target_slots if slot.get("afcCategory") == "PAF"), key=lambda item: item["start"])
    aps = [slot for slot in target_slots if slot.get("afcCategory") == "APS"]
    if len(target_slots) != len(paf) + len(aps) or len(paf) != 2 or [(slot["start"], slot["end"], _duration(slot)) for slot in paf] != [("10:30", "12:30", 120), ("13:30", "16:30", 180)] or _windows(aps) != [(510, 630)]:
        raise ValueError("Le 14/01 doit contenir 2h d’APS puis le bloc PAF de 5h.")

    # Avancer d’une heure le programme APS entre ces deux dates, sans changer
    # son ordre, ses contenus, ses affectations ou les créneaux SP intermédiaires.
    stream, windows = [], []
    for iso in sorted(by_date):
        if not first <= iso <= last:
            continue
        slots = sorted((slot for slot in by_date[iso]["slots"] if slot.get("afcCategory") == "APS"), key=lambda item: item["start"])
        if any(slot.get("uv") == "UV1" or slot.get("is_atomic") for slot in slots):
            raise ValueError("La correction PAF ne peut pas déplacer un bloc APS indivisible.")
        day_windows = _windows(slots)
        if iso == first:
            day_windows[-1] = (810, 990)
        if iso == last:
            day_windows = [(510, 570)]
        windows.extend((iso, start, end) for start, end in day_windows)
        for slot in slots:
            content = {key: deepcopy(value) for key, value in slot.items() if key not in {"start", "end", "duration", "durationMinutes"}}
            if stream and stream[-1][0] == content:
                stream[-1][1] += _duration(slot)
            else:
                stream.append([content, _duration(slot)])
    if sum(end - start for _, start, end in windows) != sum(minutes for _, minutes in stream):
        raise ValueError("La correction PAF modifierait le volume APS.")
    for iso, day in by_date.items():
        if first <= iso <= last:
            day["slots"] = [slot for slot in day["slots"] if slot.get("afcCategory") != "APS"]
    index = 0
    for iso, start, end in windows:
        while start < end:
            content, remaining = stream[index]
            duration = min(end - start, remaining)
            slot = deepcopy(content)
            slot.update(start=_hhmm(start), end=_hhmm(start + duration), durationMinutes=duration, duration=round(duration / 60, 2))
            by_date[iso]["slots"].append(slot)
            stream[index][1] -= duration
            start += duration
            if not stream[index][1]:
                index += 1
    paf[0].update(start="09:30", durationMinutes=180, duration=3)
    for slot in paf:
        slot["blockTotalMinutes"] = 360
    for iso, day in by_date.items():
        if first <= iso <= last:
            day["slots"].sort(key=lambda slot: slot["start"])
    return corrected
