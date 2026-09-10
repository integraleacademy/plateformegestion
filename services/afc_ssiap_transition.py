"""Correction ciblée de la transition APS / SSIAP approuvée le 10/09/2026."""

from copy import deepcopy


def _minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def correct_saved_ssiap_transition(planning):
    """Repositionner le SSIAP enregistré sans recalculer les autres activités."""
    corrected = deepcopy(planning)
    source = [
        (day["date"], slot)
        for day in sorted(corrected, key=lambda item: item["date"])
        for slot in sorted(day.get("slots", []), key=lambda item: item["start"])
        if slot.get("afcCategory") == "SSIAP1"
    ]
    early = [(iso, slot) for iso, slot in source if iso < "2027-01-22"]
    if not early:
        return corrected

    exams = {day["date"] for day in corrected for slot in day.get("slots", []) if slot.get("afcCategory") == "EXAM_APS"}
    if exams != {"2027-01-21"} or any(
        iso != "2027-01-20" or _minutes(slot["start"]) < 960 or _minutes(slot["end"]) > 990
        for iso, slot in early
    ) or sum(slot["durationMinutes"] for _, slot in early) != 30:
        raise ValueError("La transition enregistrée ne correspond pas au report de 30 minutes validé.")
    receiver = next((day for day in corrected if day["date"] == "2027-02-03"), None)
    if not receiver or not receiver.get("slots") or (
        {slot.get("afcCategory") for slot in receiver["slots"]} != {"SSIAP1"}
        or sum(slot["durationMinutes"] for slot in receiver["slots"]) != 360
        or max(_minutes(slot["end"]) for slot in receiver["slots"]) != 930
    ):
        raise ValueError("Le 3 février ne dispose pas du créneau SSIAP de compensation validé.")

    # Conserver le programme et ses métadonnées (intervenants, salle, notes).
    # Les fragments contigus d'une même séquence sont réunis avant redistribution.
    stream = []
    for _, slot in source:
        content = {key: deepcopy(value) for key, value in slot.items() if key not in {"start", "end", "duration", "durationMinutes"}}
        if stream and stream[-1][0] == content:
            stream[-1][1] += slot["durationMinutes"]
        else:
            stream.append([content, slot["durationMinutes"]])

    windows = [(iso, _minutes(slot["start"]), _minutes(slot["end"])) for iso, slot in source if iso >= "2027-01-22"]
    windows.append(("2027-02-03", 930, 960))
    merged_windows = []
    for iso, start, end in sorted(windows):
        if merged_windows and merged_windows[-1][0] == iso and merged_windows[-1][2] == start:
            merged_windows[-1][2] = end
        else:
            merged_windows.append([iso, start, end])
    if sum(end-start for _, start, end in merged_windows) != sum(minutes for _, minutes in stream):
        raise ValueError("Le report modifierait le volume SSIAP enregistré.")

    by_date = {day["date"]: day for day in corrected}
    for day in corrected:
        day["slots"] = [slot for slot in day.get("slots", []) if slot.get("afcCategory") != "SSIAP1"]
    index = 0
    for iso, start, end in merged_windows:
        while start < end:
            content, remaining = stream[index]
            duration = min(end-start, remaining)
            slot = deepcopy(content)
            slot.update(start=_hhmm(start), end=_hhmm(start+duration), durationMinutes=duration, duration=round(duration/60, 2))
            by_date[iso]["slots"].append(slot)
            stream[index][1] -= duration
            start += duration
            if not stream[index][1]:
                index += 1
    for day in corrected:
        day["slots"].sort(key=lambda slot: slot["start"])
    return corrected
