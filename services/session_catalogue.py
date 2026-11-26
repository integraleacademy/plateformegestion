"""The planning fields exchanged with Gestion Stagiaires. Operational files stay private."""
from datetime import date, datetime
import os
import re
from threading import Lock
from time import monotonic
from zoneinfo import ZoneInfo

import requests

from services import jury_exams

PERIODS = ("remote_start", "remote_end", "onsite_start", "onsite_end")
SLUGS = {"APS": "aps", "A3P": "a3p-apr", "DIRIGEANT": "desp-dssp", "AFC_APS_SSIAP": "afc"}
AVAILABILITY_URL = "https://gestionstagiaires-r5no.onrender.com/api/integrations/session-availability"
_counts_lock = Lock()
_counts_cache = None
_next_counts_read = 0


def registered_counts():
    """Read the same registered-trainee totals used by Gestion Stagiaires, in one batch."""
    global _counts_cache, _next_counts_read
    token = os.environ.get("SESSION_CATALOG_TOKEN")
    if not token:
        return None
    with _counts_lock:
        if monotonic() < _next_counts_read:
            return _counts_cache
        try:
            reply = requests.get(AVAILABILITY_URL, headers={"Authorization": f"Bearer {token}"},
                                 timeout=(3, 6), allow_redirects=False)
            reply.raise_for_status()
            payload = reply.json()
            if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("sessions"), list):
                raise ValueError("Invalid session availability")
            counts = {}
            for row in payload["sessions"]:
                if not isinstance(row, dict) or row.get("deleted"):
                    continue
                key, count = row.get("id"), row.get("sold")
                if not isinstance(key, str) or type(count) is not int or count < 0:
                    continue
                # SSIAP variants share a roster. Closed zero-count entries can be
                # catalogue masks for unresolved links, rather than an empty roster.
                if row.get("slug") in ("recyclage-ssiap-1", "remise-a-niveau-ssiap-1") or (row.get("visibility") == "closed" and count == 0):
                    continue
                counts[key] = None if key in counts else count
            _counts_cache = {key: count for key, count in counts.items() if count is not None}
        except (requests.RequestException, ValueError):
            _counts_cache = None
        _next_counts_read = monotonic() + 60
        return _counts_cache


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


def name(services, session):
    code = session.get("formation", "")
    return session.get("display_name") or services.SESSION_FORMATION_FILTERS.get(code, code)


def set_gestion_only(session, enabled):
    session["catalogue_gestion_only"] = enabled
    session["catalogue_touched"] = True
    if enabled and session.get("formation") == "GENERAL":
        session["catalogue_general_linked"] = True


def identity(services, session):
    kind = session.get("formation")
    slug = "ssiap-" + level(session) if kind == "SSIAP" else SLUGS.get(kind)
    if kind == "GENERAL" and session.get("catalogue_general_linked"):
        slug = "general"
    return dict(slug=slug, centre=centre(session), start=services.session_input_date(session.get("date_debut")),
                end=services.session_input_date(session.get("date_fin")), exam=services.session_input_date(session.get("date_exam")),
                standard_start=session.get("catalogue_standard_start", "") if slug == "ssiap-1" else "")


def edit_fields(services, session, form, previous=None):
    previous_start = services.session_input_date((previous or {}).get("date_debut"))
    new_start = services.session_input_date(session.get("date_debut"))
    rescheduled = bool(previous_start and new_start and previous_start != new_start)
    if "session_name" in form:
        chosen = form["session_name"].strip()
        if len(chosen) > 80:
            raise ValueError("Le nom de la session est limité à 80 caractères.")
        if chosen or previous is not None:
            session["display_name"] = chosen
    if session.get("date_debut") and session.get("date_fin") and session["date_fin"] < session["date_debut"]:
        raise ValueError("La fin de la session doit suivre son début.")
    if "catalogue_scope_form" in form:
        set_gestion_only(session, form.get("catalogue_gestion_only") == "1")
    if session.get("formation") == "GENERAL":
        return
    session["catalogue_touched"] = True
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
        if value not in ("public", "internal", "match"):
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
        if rescheduled and value and value == previous.get("catalogue_standard_start"):
            value = shifted(value, previous_start, new_start)
        if not new_start or not session.get("date_fin"):
            value = ""
        if value and (services.session_input_date(value) != value or not new_start < value <= session["date_fin"]):
            raise ValueError("Le début sans SST doit se situer après le début avec SST et dans la période de la session.")
        session["catalogue_standard_start"] = value
    if session.get("formation") == "DIRIGEANT" and "dirigeant_location" in form:
        location = form["dirigeant_location"].upper()
        if location not in services.DIRIGEANT_LOCATIONS:
            raise ValueError("Choisissez le centre du DESP.")
        if previous and previous.get("dirigeant_location") != location:
            session.pop("catalogue_venue", None)
        session.update(dirigeant_location=location, dirigeant_location_label=services.DIRIGEANT_LOCATIONS[location])
    if session.get("formation") == "AFC_APS_SSIAP":
        session["catalogue_visibility"] = "internal"
    if "catalogue_target_id" in form:
        target = form["catalogue_target_id"].strip()
        if target and not re.fullmatch(r"[\w-]{1,64}", target, re.ASCII):
            raise ValueError("L’identifiant Gestion Stagiaires est invalide.")
        session["catalogue_target_id"] = target
    if session.get("formation") in ("APS", "A3P", "DIRIGEANT"):
        cleared = set(session.get("catalogue_cleared_periods", []))
        for field in PERIODS:
            if field in form:
                value = form[field].strip()
                if value and (not services.session_input_date(value) or services.session_input_date(value) != value):
                    raise ValueError("Vérifiez les dates des périodes de formation.")
                if value:
                    cleared.discard(field)
                elif previous and previous.get(field):
                    cleared.add(field)
                session[field] = value
        if cleared or "catalogue_cleared_periods" in session:
            session["catalogue_cleared_periods"] = sorted(cleared)
        for start, end in (("remote_start", "remote_end"), ("onsite_start", "onsite_end")):
            if rescheduled and previous.get(start) and previous.get(end) and all(
                    session.get(k) == previous.get(k) for k in (start, end)):
                session[start] = shifted(services.session_input_date(previous[start]), previous_start, new_start)
                session[end] = shifted(services.session_input_date(previous[end]), previous_start, new_start)

            if not new_start or not session.get("date_fin"):
                session[start] = session[end] = ""
                continue
            lo, hi = session.get(start), session.get(end)
            if bool(lo) != bool(hi) or (lo and (hi < lo or lo < session["date_debut"] or hi > session["date_fin"])):
                raise ValueError("Renseignez les deux dates de chaque période dans les limites de la session.")


def shifted(value, old_start, new_start):
    try:
        return (date.fromisoformat(value) + (date.fromisoformat(new_start) - date.fromisoformat(old_start))).isoformat()
    except (ValueError, TypeError):
        raise ValueError("Vérifiez les dates du report de la session.") from None


def rows(services, sessions, *, include_past=False):
    today = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
    result = []
    for session in sessions:
        key = identity(services, session)
        if not key["slug"] or not session.get("id"):
            continue
        undated = not key["start"] or not key["end"]
        if (undated or key["end"] < today) and not (include_past or session.get("catalogue_touched")):
            continue
        visibility = session.get("catalogue_visibility", "match")
        if session.get("archived") or (not undated and key["end"] < key["start"]):
            visibility = "closed"
        elif key["slug"] == "afc" or not key["centre"]:
            visibility = "internal"
        withdrawn = key["slug"] == "general" and not session.get("catalogue_gestion_only")
        if withdrawn:
            visibility = "closed"
        only = bool(session.get("catalogue_gestion_only"))
        item = {**key, "id": session["id"], "name": name(services, session),
                "custom_name": bool(session.get("display_name")), "gestion_only": only,
                "venue": session.get("catalogue_venue", ""), "deleted": withdrawn, "unscheduled": undated,
                "edited": bool(session.get("catalogue_touched")), "capacity": session.get("catalogue_capacity", 12),
                "visibility": visibility, "target": session.get("catalogue_target_id", ""),
                "aliases": session.get("catalogue_aliases", [])}
        for prefix, modality in (("remote", "elearning"), ("onsite", "presentiel")):
            period = {} if undated else services.session_modality_date_range(session, modality) or {}
            for boundary in ("start", "end"):
                item[prefix + "_" + boundary] = period.get(boundary, "")
        if key["slug"] == "afc":
            exams = jury_exams.exam_dates(services, session)
            item.update(exam=exams["aps"], ssiap_exam=exams["ssiap1"])
        result.append(item)
    return sorted(result, key=lambda row: row["id"])

def remember_deletion(services, data, session):
    emitted = rows(services, [session], include_past=True)
    if emitted:
        row = emitted[0]
        data.setdefault("catalogue_deletions", {})[row["id"]] = {
            **row, "visibility": "closed", "deleted": True, "name": "", "custom_name": False, "venue": "",
        }
