"""Correction du volume RAN confirmé à 54 h, sans réaffectation à un autre module."""

from copy import deepcopy


def _duration(slot):
    return int(slot.get("durationMinutes") or round(float(slot.get("duration") or 0) * 60))


def correct_afc_ran_hours(planning):
    corrected = deepcopy(planning)
    total = sum(_duration(slot) for day in corrected for slot in day.get("slots", []) if slot.get("afcCategory") == "RAN")
    if total == 54 * 60:
        return corrected
    if total != 55 * 60:
        raise ValueError("La correction RAN attend un ancien volume de 55h ou un volume déjà corrigé de 54h.")
    # Retirer l'heure excédentaire de la dernière journée RAN complète.
    # Toutes les journées restent entre 6 et 7 h et les autres activités sont inchangées.
    candidates = [day for day in corrected if day.get("slots")
                  and all(slot.get("afcCategory") == "RAN" for slot in day["slots"])
                  and sum(_duration(slot) for slot in day["slots"]) == 420]
    if not candidates:
        raise ValueError("Aucune journée complète de RAN ne permet de retirer 1h en conservant au moins 6h de cours.")
    selected = max(candidates, key=lambda day: day["date"])
    remaining = 60
    for slot in sorted(selected["slots"], key=lambda slot: slot["start"], reverse=True):
        if not remaining:
            break
        start_h, start_m = map(int, slot["start"].split(":"))
        end_h, end_m = map(int, slot["end"].split(":"))
        duration = _duration(slot)
        if (end_h - start_h) * 60 + end_m - start_m != duration or duration <= 0:
            raise ValueError("Un créneau RAN présente une durée incohérente.")
        removed = min(remaining, duration)
        end = end_h * 60 + end_m - removed
        slot.update(end=f"{end // 60:02d}:{end % 60:02d}", durationMinutes=duration - removed, duration=round((duration - removed) / 60, 2))
        remaining -= removed
    selected["slots"] = [slot for slot in selected["slots"] if slot["durationMinutes"] > 0]
    return corrected
