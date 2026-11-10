from copy import deepcopy


TARGET_DATES = [
    "2026-11-16",
    "2026-11-19",
    "2026-11-23",
    "2026-11-26",
    "2026-11-30",
    "2026-12-03",
    "2026-12-07",
    "2026-12-10",
    "2026-12-14",
    "2027-01-07",
    "2027-01-11",
]


def _minutes(value):
    hour, minute = [int(part) for part in value.split(":")[:2]]
    return hour * 60 + minute


def _hhmm(total):
    return f"{total // 60:02d}:{total % 60:02d}"


def shift_11am_training_days(planning):
    """Shift every A3P day starting at 11:00 by one hour, preserving durations and breaks."""
    corrected = deepcopy(planning or [])
    by_date = {day.get("date"): day for day in corrected}

    missing = [date for date in TARGET_DATES if date not in by_date]
    if missing:
        raise ValueError(
            "Décalage des journées de 11h impossible : dates absentes du planning : " + ", ".join(missing)
        )

    shifted_dates = []
    for date in TARGET_DATES:
        day = by_date[date]
        slots = day.get("slots") or []
        if not slots:
            raise ValueError(f"Décalage impossible : aucun créneau le {date}.")
        first_start = min(_minutes(slot.get("start")) for slot in slots)
        if first_start != 11 * 60:
            raise ValueError(
                f"Décalage non appliqué : la journée du {date} ne commence plus à 11:00 "
                f"(début actuel {_hhmm(first_start)})."
            )

        shifted = []
        for raw_slot in slots:
            slot = dict(raw_slot)
            start = _minutes(slot.get("start")) + 60
            end = _minutes(slot.get("end")) + 60
            if end >= 24 * 60:
                raise ValueError(f"Décalage impossible le {date} : un créneau dépasserait minuit.")
            slot["start"] = _hhmm(start)
            slot["end"] = _hhmm(end)
            slot["durationMinutes"] = end - start
            shifted.append(slot)
        day["slots"] = shifted
        shifted_dates.append(date)

    return corrected, shifted_dates
