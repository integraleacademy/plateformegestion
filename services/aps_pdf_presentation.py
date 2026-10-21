"""Readable APS PDF labels and blocks, separate from the canonical curriculum."""

from copy import deepcopy
from decimal import Decimal
import re


APS_CONTRACT_PRESENTATION_VERSION = "aps-modules-v1"


APS_MODULE_NAMES = {
    "UV1": "Secourisme",
    "UV2": "Environnement juridique",
    "UV3": "Gestion des conflits",
    "UV4": "Stratégique",
    "UV5": "Prévention des risques d’incendie",
    "UV6": "Modalité d’appréhension au cours de l’exercice du métier",
    "UV7": "Sensibilisation aux risques terroristes",
    "UV8": "Professionnel",
    "UV9": "Palpation de sécurité et inspection des bagages",
    "UV10": "Surveillance par moyens électroniques de sécurité",
    "UV11": "Gestion des risques",
    "UV12": "Évènementiel spécifique",
    "UV13": "Gestion des situations conflictuelles dégradées",
    "UV14": "Industriel spécifique",
}


def module_label(uv):
    return f"UV {uv[2:]} - Module {APS_MODULE_NAMES[uv]}"


def compact_planning_for_pdf(planning):
    """Merge contiguous module blocks without crossing breaks or teacher changes."""
    result = deepcopy(planning)
    for day in result:
        merged = []
        for slot in day.get("slots", []):
            uv = slot.get("uv")
            if uv in APS_MODULE_NAMES:
                slot["apsDisplayTitle"] = module_label(uv)
            slot["durationMinutes"] = int(round(slot.get("durationMinutes") or slot.get("duration", 0) * 60))
            previous = merged[-1] if merged else None
            same_module = previous and uv in APS_MODULE_NAMES and all(
                (previous.get(key) or "") == (slot.get(key) or "")
                for key in ("uv", "modality", "room", "trainer", "part")
            )
            if same_module and previous.get("end") == slot.get("start"):
                previous["end"] = slot["end"]
                previous["durationMinutes"] += slot["durationMinutes"]
                previous["duration"] = previous["durationMinutes"] / 60
                previous["practiceMinutes"] = previous.get("practiceMinutes", 0) + slot.get("practiceMinutes", 0)
                previous["deliveryType"] = (
                    "practice" if previous["practiceMinutes"] == previous["durationMinutes"]
                    else "mixed" if previous["practiceMinutes"] else "theory"
                )
            else:
                merged.append(slot)
        day["slots"] = merged
    return result


def module_summary_rows(summary):
    """One row per UV, with separate distance/on-site hours and an exact total."""
    modalities = summary.get("modality_uv_totals") or {}
    return [
        {"uv": uv, "label": module_label(uv),
         "hours": summary["uv_totals"].get(uv, 0),
         "elearningHours": modalities.get("elearning", {}).get(uv, 0),
         "presentielHours": modalities.get("presentiel", {}).get(uv, 0)}
        for uv in APS_MODULE_NAMES
    ]


def contract_interventions_for_pdf(interventions):
    """Present saved contract snapshots using the same modules as the planning.

    Older contracts only store a combined ``module`` string, without a UV key.
    Work on a copy so the contractual hours and canonical source stay intact.
    """
    result = []
    for row in deepcopy(interventions):
        match = re.match(r"^UV\s*(\d+)\b", str(row.get("module") or "").strip(), re.IGNORECASE)
        uv = f"UV{match.group(1)}" if match else None
        if uv in APS_MODULE_NAMES:
            row["module"] = module_label(uv)
        previous = result[-1] if result else None
        same_block = previous and uv in APS_MODULE_NAMES and all(
            (previous.get(key) or "") == (row.get(key) or "")
            for key in ("date", "module", "modality", "room", "trainer", "part")
        )
        if same_block and row.get("date") and row.get("start") and previous.get("end") == row["start"]:
            previous["end"] = row["end"]
            previous["hours"] = float(Decimal(str(previous.get("hours") or 0)) + Decimal(str(row.get("hours") or 0)))
        else:
            result.append(row)
    return result


def contract_module_labels(interventions):
    """List each assigned module once, in numeric UV order."""
    order = {module_label(uv): index for index, uv in enumerate(APS_MODULE_NAMES)}
    labels = {str(row.get("module") or "").strip() for row in interventions}
    return sorted(labels - {""}, key=lambda label: (order.get(label, len(order)), label))
