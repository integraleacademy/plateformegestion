"""Adopt the dated training groups announced on the public website on 25 November 2026."""
import csv
from datetime import datetime
from pathlib import Path
import threading
import uuid
from zoneinfo import ZoneInfo

from services import session_catalogue

MANIFEST = Path(__file__).with_name("published_sessions_2027.csv")
RECEIPT = "import_public_sessions_2027_v1"


def reconcile(services, data, offers, today):
    if RECEIPT in data:
        return False
    original = [(row, session_catalogue.identity(services, row)) for row in data["sessions"]]
    receipt = {"created": [], "linked": [], "skipped": []}
    kinds = {code: kind for kind, code in session_catalogue.SLUGS.items()}
    for offer in offers:
        if offer["start"] < today:
            continue
        group = [(row, key) for row, key in original if (key["slug"], key["centre"]) == (offer["slug"], offer["centre"])]
        def agrees(key):
            return sum(bool(offer[k]) and key.get(k) == offer[k] for k in ("start", "end", "exam")) >= 2
        matches = [row for row, key in group if agrees(key) or any(agrees(a) and a.get("slug")==offer["slug"] and a.get("centre")==offer["centre"] for a in row.get("catalogue_aliases", []))]
        name = "/".join(offer[k] for k in ("slug", "centre", "start"))
        if len(matches) > 1 or matches and (matches[0].get("archived") or matches[0].get("catalogue_visibility") in ("closed", "internal")):
            receipt["skipped"].append(name)
            continue
        if matches:
            session = matches[0]
            # The operational plan takes precedence whenever the published breakdown differs.
            key = session_catalogue.identity(services, session)
            unchanged = (key["start"], key["end"]) == (offer["start"], offer["end"])
            receipt["linked"].append(session["id"])
        else:
            if any(key["start"] and key["end"] and key["start"] <= offer["end"] and offer["start"] <= key["end"] for row, key in group):
                receipt["skipped"].append(name)
                continue
            kind = "SSIAP" if offer["slug"].startswith("ssiap-") else kinds[offer["slug"]]
            sid = uuid.uuid5(uuid.NAMESPACE_URL, "https://integraleacademyofficiel-1.onrender.com/planning/" + name).hex[:12]
            if any(s.get("id") == sid for s in data["sessions"]):
                raise ValueError("Identifiant du planning public déjà attribué")
            session = dict(id=sid, formation=kind, date_debut=offer["start"], date_fin=offer["end"], date_exam=offer["exam"],
                           color=services.FORMATION_COLORS[kind], steps=services.default_steps_for(kind), archived=False,
                           jurys=[], jury_notification_status="to_notify", created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            if kind == "DIRIGEANT":
                location = offer["centre"].upper()
                session.update(dirigeant_location=location, dirigeant_location_label=services.DIRIGEANT_LOCATIONS[location])
                if location == "PARIS":
                    session["salle"] = "Intégrale Academy – 34 rue Poissonnière – 75002 Paris"
            if kind == "SSIAP":
                level = offer["slug"][-1]
                session.update(ssiap_level=level, training_code="SSIAP"+level, display_name="SSIAP "+level)
            data["sessions"].append(session)
            receipt["created"].append(sid)
            unchanged = True
        session.setdefault("catalogue_visibility", "public")
        session.setdefault("catalogue_capacity", int(offer["capacity"]))
        if unchanged:
            if offer["standard_start"]:
                session.setdefault("catalogue_standard_start", offer["standard_start"])
            for field in session_catalogue.PERIODS:
                modality = "elearning" if field.startswith("remote") else "presentiel"
                period = services.session_modality_date_range(session, modality) or {}
                if offer[field] and not period.get(field.split("_")[1]):
                    session.setdefault(field, offer[field])
    data[RECEIPT] = receipt
    return True


def adopt_public_form_session(services, data, today):
    # This existing APS group was offered in the public information form at cutover.
    # Its absence from the website catalogue must not create a second group.
    receipt = data[RECEIPT]
    if "information_form" in receipt:
        return False
    receipt["information_form"] = []
    for session in data["sessions"]:
        if (session.get("id") != "7b549596" or session.get("archived") or session.get("catalogue_visibility", "match") != "match"):
            continue
        key = session_catalogue.identity(services, session)
        if (today <= key["start"] and (key["slug"], key["centre"], key["start"], key["end"], key["exam"]) ==
                ("aps", "puget", "2027-02-04", "2027-03-10", "2027-03-11")):
            session["catalogue_visibility"] = "public"
            receipt["information_form"].append(session["id"])
    return True


def start(services):
    import os
    if os.getenv("RENDER_SERVICE_ID") != "srv-d3kj73muk2gs73fao7ug":
        return
    def run():
        from time import sleep
        for delay in (2, 5, 15, 30, 60):
            try:
                data = services.load_sessions()
                today = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
                changed = False
                if RECEIPT not in data:
                    with MANIFEST.open(encoding="utf-8", newline="") as stream:
                        changed = reconcile(services, data, csv.DictReader(stream), today)
                changed = adopt_public_form_session(services, data, today) or changed
                if changed:
                    services.save_sessions(data)
                    services.app.logger.info("Planning public repris : %s", {key:len(value) for key,value in data[RECEIPT].items()})
                return
            except Exception as exc:
                services.app.logger.warning("Reprise du planning public en attente (%s)", type(exc).__name__)
                sleep(delay)
    threading.Thread(target=run, daemon=True, name="reprise-planning-public").start()
