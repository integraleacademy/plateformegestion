from copy import deepcopy

from a3p_program import A3P_MODULE_BY_CODE


TARGET_DAYS = {
    "2026-11-17": [("09:00", "13:00", "UV4"), ("14:00", "18:00", "UV6B")],
    "2026-11-18": [("09:00", "13:00", "UV6B"), ("14:00", "18:00", "UV6B")],
    "2026-12-15": [("09:00", "13:00", "UV6B"), ("14:00", "17:00", "UV6B"), ("17:00", "18:00", "UV7")],
    "2026-12-18": [("09:00", "13:00", "UV7"), ("14:00", "18:00", "UV7")],
    "2026-12-21": [("09:00", "13:00", "UV7"), ("14:00", "18:00", "UV7")],
}


def _minutes(value):
    hour, minute = [int(part) for part in value.split(":")[:2]]
    return hour * 60 + minute


def _signature(day):
    return [
        (slot.get("start"), slot.get("end"), (slot.get("code") or slot.get("uv") or "").upper())
        for slot in day.get("slots") or []
    ]


def _slot(start, end, code, trainer, room):
    return {
        "start": start,
        "end": end,
        "durationMinutes": _minutes(end) - _minutes(start),
        "code": code,
        "title": A3P_MODULE_BY_CODE[code]["title"],
        "locked": False,
        "placementMode": "manuel",
        "trainer": trainer,
        "room": room,
    }


def correct_session_f3c27cf4_a3p_planning(planning):
    """Apply the 17-18 Nov 2026 field/pool change while preserving all A3P hour totals."""
    corrected = deepcopy(planning or [])
    by_date = {day.get("date"): day for day in corrected}

    missing = [date for date in TARGET_DAYS if date not in by_date]
    if missing:
        raise ValueError("Correction A3P impossible : journées absentes du planning : " + ", ".join(missing))

    for date, expected in TARGET_DAYS.items():
        actual = _signature(by_date[date])
        if actual != expected:
            raise ValueError(
                f"Correction A3P non appliquée : le planning du {date} a changé depuis la version attendue "
                f"(attendu {expected}, actuel {actual})."
            )

    fallback_slots = [slot for day in corrected for slot in day.get("slots") or []]
    default_trainer = next((str(slot.get("trainer") or "").strip() for slot in fallback_slots if str(slot.get("trainer") or "").strip()), "")
    default_room = next((str(slot.get("room") or "").strip() for slot in fallback_slots if str(slot.get("room") or "").strip()), "")

    def context(date):
        slots = by_date[date].get("slots") or []
        trainer = next((str(slot.get("trainer") or "").strip() for slot in slots if str(slot.get("trainer") or "").strip()), default_trainer)
        room = next((str(slot.get("room") or "").strip() for slot in slots if str(slot.get("room") or "").strip()), default_room)
        return trainer, room

    trainer, room = context("2026-11-17")
    by_date["2026-11-17"]["slots"] = [
        _slot("09:00", "13:00", "UV7", trainer, "Extérieur"),
        _slot("14:00", "18:00", "UV7", trainer, "Extérieur"),
    ]

    trainer, room = context("2026-11-18")
    by_date["2026-11-18"]["slots"] = [
        _slot("10:30", "12:00", "UV7", trainer, "Piscine Galieni"),
        _slot("13:00", "19:30", "UV6B", trainer, room),
    ]

    trainer, room = context("2026-12-15")
    by_date["2026-12-15"]["slots"] = [
        _slot("09:00", "13:00", "UV6B", trainer, room),
        _slot("14:00", "17:00", "UV6B", trainer, room),
        _slot("17:00", "18:00", "UV4", trainer, room),
    ]

    trainer, room = context("2026-12-18")
    by_date["2026-12-18"]["slots"] = [
        _slot("09:00", "12:00", "UV4", trainer, room),
        _slot("12:00", "13:00", "UV6B", trainer, room),
        _slot("14:00", "18:00", "UV6B", trainer, room),
    ]

    trainer, room = context("2026-12-21")
    by_date["2026-12-21"]["slots"] = [
        _slot("09:00", "09:30", "UV6B", trainer, room),
        _slot("09:30", "13:00", "UV7", trainer, room),
        _slot("14:00", "18:00", "UV7", trainer, room),
    ]

    return corrected
