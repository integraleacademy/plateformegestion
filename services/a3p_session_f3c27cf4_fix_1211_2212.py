from copy import deepcopy

from a3p_program import A3P_MODULE_BY_CODE


EXPECTED = {
    "2026-11-12": [
        ("11:00", "15:00", "UV2"),
        ("16:00", "18:00", "UV2"),
        ("18:00", "20:00", "UV3"),
    ],
    "2026-12-22": [
        ("01:00", "02:00", "UV7"),
        ("12:00", "15:30", "UV9"),
        ("16:30", "20:00", "UV9"),
    ],
}


def _minutes(value):
    hour, minute = [int(part) for part in value.split(":")[:2]]
    return hour * 60 + minute


def _signature(day):
    return [
        (slot.get("start"), slot.get("end"), (slot.get("code") or slot.get("uv") or "").upper())
        for slot in day.get("slots") or []
    ]


def _slot(start, end, code, template):
    result = dict(template or {})
    result.update({
        "start": start,
        "end": end,
        "durationMinutes": _minutes(end) - _minutes(start),
        "code": code,
        "title": A3P_MODULE_BY_CODE[code]["title"],
        "locked": bool(result.get("locked")),
        "placementMode": result.get("placementMode") or ("manuel" if result.get("locked") else "automatique"),
    })
    result.pop("uv", None)
    return result


def correct_1211_and_2212(planning):
    """Correct 12 Nov to 12:00-21:00 and replace the 22 Dec 01:00 typo by a noon start."""
    corrected = deepcopy(planning or [])
    by_date = {day.get("date"): day for day in corrected}

    for date, expected in EXPECTED.items():
        day = by_date.get(date)
        if not day:
            raise ValueError(f"Correction impossible : journée {date} absente du planning.")
        actual = _signature(day)
        if actual != expected:
            raise ValueError(
                f"Correction non appliquée : le planning du {date} a changé "
                f"(attendu {expected}, actuel {actual})."
            )

    day = by_date["2026-11-12"]
    old = day["slots"]
    day["slots"] = [
        _slot("12:00", "16:00", "UV2", old[0]),
        _slot("17:00", "19:00", "UV2", old[1]),
        _slot("19:00", "21:00", "UV3", old[2]),
    ]

    day = by_date["2026-12-22"]
    old = day["slots"]
    day["slots"] = [
        _slot("12:00", "13:00", "UV7", old[0]),
        _slot("13:00", "16:30", "UV9", old[1]),
        _slot("17:30", "21:00", "UV9", old[2]),
    ]

    return corrected
