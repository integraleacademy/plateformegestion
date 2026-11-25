"""The planning fields exchanged with Gestion Stagiaires. Operational files stay private."""
from datetime import datetime
import re
from zoneinfo import ZoneInfo

from services import jury_exams

PERIODS = ("remote_start", "remote_end", "onsite_start", "onsite_end")
SLUGS = {"APS": "aps", "A3P": "a3p-apr", "DIRIGEANT": "desp-dssp", "AFC_APS_SSIAP": "afc"}


def level(session):
    match = re.search(r"SSIAP\s*([123])", str(session.get("display_name") or ""), re.I)
    return str(session.get("ssiap_level") or (match[1] if match else "1"))


def centre(session):
    if session.get("formation") != "DIRIGEANT":
        return "puget"
    value = str(session.get("dirigeant_location") or session.get("display_name") or "").lower()
    if "paris" in value:
        return "paris"
    if "puget" in value or "azur" in value:
        return "puget"
    return ""


def identity(services, session):
    kind = session.get("formation")
    slug = "ssiap-" + level(session) if kind == "SSIAP" else SLUGS.get(kind)
    return dict(slug=slug, centre=centre(session), start=services.session_input_date(session.get("date_debut")),
                end=services.session_input_date(session.get("date_fin")), exam=services.session_input_date(session.get("date_exam")))


def edit_fields(services, session, form):
    if session.get("formation") == "GENERAL":
        return
    if "catalogue_capacity" in form:
        try:
            capacity = int(form["catalogue_capacity"])
            if not 1 <= capacity <= 12:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("La capacité doit être comprise entre 1 et 12 places.") from None
        session["catalogue_capacity"] = capacity
    if "catalogue_visibility" in form:
        value = form["catalogue_visibility"]
        if value not in ("public", "internal"):
            raise ValueError("Choisissez le mode de publication.")
        session["catalogue_visibility"] = value
    if session.get("formation") == "SSIAP" and "ssiap_level" in form:
        if form["ssiap_level"] not in ("1", "2", "3"):
            raise ValueError("Choisissez le niveau SSIAP.")
        if not session.get("display_name") or re.fullmatch(r"SSIAP\s*[123]?", session["display_name"], re.I):
            session["display_name"] = "SSIAP " + form["ssiap_level"]
        session.update(ssiap_level=form["ssiap_level"], training_code="SSIAP" + form["ssiap_level"])
    if session.get("formation") == "SSIAP" and "catalogue_standard_start" in form:
        value = form["catalogue_standard_start"].strip() if level(session) == "1" else ""
        if value and (services.session_input_date(value) != value or not session["date_debut"] < value <= session["date_fin"]):
            raise ValueError("Le début sans SST doit se situer après le début avec SST et dans la période de la session.")
        session["catalogue_standard_start"] = value
    if session.get("formation") == "DIRIGEANT" and "dirigeant_location" in form:
        location = form["dirigeant_location"].upper()
        if location not in services.DIRIGEANT_LOCATIONS:
            raise ValueError("Choisissez le centre du DESP.")
        session.update(dirigeant_location=location, dirigeant_location_label=services.DIRIGEANT_LOCATIONS[location])
    if session.get("formation") == "AFC_APS_SSIAP":
        session["catalogue_visibility"] = "internal"
    if "catalogue_target_id" in form:
        target = form["catalogue_target_id"].strip()
        if target and not re.fullmatch(r"[\w-]{1,64}", target, re.ASCII):
            raise ValueError("L’identifiant Gestion Stagiaires est invalide.")
        session["catalogue_target_id"] = target
    if session.get("formation") in ("APS", "A3P", "DIRIGEANT"):
        for field in PERIODS:
            if field in form:
                value = form[field].strip()
                if value and (not services.session_input_date(value) or services.session_input_date(value) != value):
                    raise ValueError("Vérifiez les dates des périodes de formation.")
                session[field] = value
        for start, end in (("remote_start", "remote_end"), ("onsite_start", "onsite_end")):
            lo, hi = session.get(start), session.get(end)
            if bool(lo) != bool(hi) or (lo and (hi < lo or lo < session["date_debut"] or hi > session["date_fin"])):
                raise ValueError("Renseignez les deux dates de chaque période dans les limites de la session.")


def rows(services, sessions):
    today = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
    result = []
    for session in sessions:
        key = identity(services, session)
        if not key["slug"] or not key["start"] or not key["end"] or key["end"] < today or not session.get("id"):
            continue
        visibility = session.get("catalogue_visibility", "match")
        if session.get("archived") or key["end"] < key["start"]:
            visibility = "closed"
        elif key["slug"] == "afc" or not key["centre"]:
            visibility = "internal"
        item = {**key, "id": session["id"], "capacity": session.get("catalogue_capacity", 12),
                "visibility": visibility, "target": session.get("catalogue_target_id", ""),
                "aliases": session.get("catalogue_aliases", []),
                "standard_start": session.get("catalogue_standard_start", "") if key["slug"] == "ssiap-1" else ""}
        for prefix, modality in (("remote", "elearning"), ("onsite", "presentiel")):
            period = services.session_modality_date_range(session, modality) or {}
            for boundary in ("start", "end"):
                field = prefix + "_" + boundary
                item[field] = session.get(field) or services.session_input_date(period.get(boundary))
        if key["slug"] == "afc":
            exams = jury_exams.exam_dates(services, session)
            item.update(exam=exams["aps"], ssiap_exam=exams["ssiap1"])
        result.append(item)
    return sorted(result, key=lambda row: row["id"])
