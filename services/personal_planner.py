"""Shared private planner. Personal data stays on the persistent disk.

Training milestones are a read-only projection of the existing sessions store.
SQLite transactions and per-record revisions protect simultaneous edits by the
two users and the two Gunicorn workers; no whole-document overwrite is used.
"""
from contextlib import closing
from datetime import date, datetime, timedelta
from io import BytesIO
import hmac
import json
import os
import re
import secrets
import sqlite3
import uuid
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, render_template, request, session, send_file

KINDS = {"location", "louise", "boarding", "transport", "personal", "professional", "shopping", "task", "note"}
OWNERS = {"both", "clement", "elsa"}
PLACES = {"paris": "Paris", "puget": "Puget", "cantal": "Cantal", "away": "Déplacement"}
STATUSES = {"pending", "booked", "needs_change", "not_needed"}
STATUS_LABELS = {"pending": "À réserver", "booked": "Réservé", "needs_change": "À modifier", "not_needed": "Pas nécessaire"}
ITEMS = {"shopping", "task", "note"}


class PlannerError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def day(value, label="Date"):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise PlannerError(f"{label} : renseignez une date valide.")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise PlannerError(f"{label} : renseignez une date valide.") from None
    if not 2000 <= result.year <= 2100:
        raise PlannerError(f"{label} : choisissez une année entre 2000 et 2100.")
    return result


def date_range(start, end):
    current = day(start)
    last = day(end)
    while current <= last:
        yield current.isoformat()
        current += timedelta(days=1)


def text_field(data, key, limit=300):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > limit:
        raise PlannerError(f"Le champ {key} doit contenir au maximum {limit} caractères.")
    return value.strip()


def validate(data):
    if not isinstance(data, dict):
        raise PlannerError("Les informations envoyées sont invalides.")
    kind = data.get("kind")
    if not isinstance(kind, str) or kind not in KINDS or not isinstance(data.get("owner", "both"), str) or data.get("owner", "both") not in OWNERS:
        raise PlannerError("Choisissez une catégorie et une personne valides.")
    result = {"kind": kind, "owner": data.get("owner", "both"),
              "title": text_field(data, "title", 200), "notes": text_field(data, "notes", 20000)}
    if kind not in ITEMS:
        start = day(data.get("start"), "Date de début")
        end = day(data.get("end") or data.get("start"), "Date de fin")
        if end < start or (end - start).days > 1096:
            raise PlannerError("La fin doit suivre le début, dans une limite de trois ans.")
        result.update(start=start.isoformat(), end=end.isoformat())
        for key in ("start_time", "end_time"):
            value = text_field(data, key, 5)
            if value and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
                raise PlannerError("Renseignez une heure valide.")
            result[key] = value
        if start == end and result["start_time"] and result["end_time"] and result["end_time"] < result["start_time"]:
            raise PlannerError("L’heure de fin doit suivre l’heure de début.")
    else:
        result["done"] = data.get("done") is True
        result["quantity"] = text_field(data, "quantity", 80)
        result["due"] = day(data["due"]).isoformat() if data.get("due") else ""
    if kind == "location":
        place = data.get("place")
        if not isinstance(place, str) or place not in PLACES:
            raise PlannerError("Choisissez Paris, Puget, le Cantal ou un déplacement.")
        result.update(place=place, destination=text_field(data, "destination"))
        if place == "away" and not result["destination"]:
            raise PlannerError("Indiquez la destination de votre déplacement.")
        result["title"] = result["destination"] if place == "away" else PLACES[place]
        for prefix in ("boarding", "transport"):
            status = data.get(prefix + "_status", "pending" if place in {"paris", "away"} else "not_needed")
            if not isinstance(status, str) or status not in STATUSES:
                raise PlannerError("Choisissez un statut de réservation valide.")
            result[prefix + "_status"] = status
            result[prefix + "_notes"] = text_field(data, prefix + "_notes", 10000)
            if status != "not_needed":
                # Keep planned / existing booking dates when its status changes.
                first_value = data.get(prefix + "_start")
                first = day(first_value or (None if status == "booked" else result["start"]), "Début de réservation")
                last_value = data.get(prefix + "_end")
                if not last_value and status != "booked":
                    last_value = result["end"]
                last = day(last_value, "Fin de réservation / retour") if last_value else first
                if last < first or (last - first).days > 1096:
                    raise PlannerError("Vérifiez les dates de réservation.")
                result[prefix + "_start"] = first.isoformat()
                result[prefix + "_end"] = last.isoformat() if prefix == "boarding" or last_value else ""
        result["transport_round_trip"] = data.get("transport_round_trip") is not False
        if not result["transport_round_trip"]:
            result["transport_end"] = ""
        result["transport_mode"] = text_field(data, "transport_mode", 40) or "Avion"
        result["transport_origin"] = text_field(data, "transport_origin")
    if kind in {"boarding", "transport"}:
        result["status"] = data.get("status", "pending")
        if not isinstance(result["status"], str) or result["status"] not in STATUSES:
            raise PlannerError("Choisissez un statut de réservation valide.")
        for key in ("origin", "destination", "reference", "mode"):
            result[key] = text_field(data, key)
        if kind == "transport" and (not result["origin"] or not result["destination"]):
            raise PlannerError("Indiquez le départ et l’arrivée du trajet.")
    if not result["title"]:
        result["title"] = {"louise": "Avec Louise", "boarding": "Pension chien", "transport": "Trajet"}.get(kind, "")
    if not result["title"]:
        raise PlannerError("Ajoutez un intitulé.")
    return result


def people(record):
    return {"clement", "elsa"} if record["owner"] == "both" else {record["owner"]}


def read_records(db):
    return [dict(json.loads(row["payload"]), id=row["id"], revision=row["revision"])
            for row in db.execute("SELECT id, payload, revision FROM planner_records ORDER BY id")]


def connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("CREATE TABLE IF NOT EXISTS planner_records (id TEXT PRIMARY KEY, payload TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1)")
    return db


def put_record(db, record, record_id=None, revision=1):
    rid = record_id or uuid.uuid4().hex
    payload = {key: val for key, val in record.items() if key not in {"id", "revision"}}
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    db.execute("INSERT INTO planner_records(id,payload,revision) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, revision=excluded.revision",
               (rid, json.dumps(payload, ensure_ascii=False), revision))
    return rid


def location_overlap(candidate, records):
    for record in records:
        if record["kind"] != "location" or record.get("id") == candidate.get("id"):
            continue
        shared = people(candidate) & people(record)
        if shared and candidate["start"] <= record["end"] and record["start"] <= candidate["end"]:
            who = " et ".join("Clément" if p == "clement" else "Elsa" for p in sorted(shared))
            when = max(candidate["start"], record["start"])
            raise PlannerError(f"Un lieu est déjà renseigné pour {who} le {day(when).strftime('%d/%m/%Y')}. Modifiez cette période ou utilisez « Remplir seulement les jours sans lieu ».", 409)


def ranges(days):
    """Compact a sorted list of date strings into inclusive periods."""
    result = []
    for value in sorted(set(days)):
        if result and day(result[-1][1]) + timedelta(days=1) == day(value):
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def fill_locations(candidate, records):
    by_owner = {}
    for person in sorted(people(candidate)):
        covered = {value for r in records if r["kind"] == "location" and person in people(r)
                   for value in date_range(max(candidate["start"], r["start"]), min(candidate["end"], r["end"]))}
        by_owner[person] = ranges(value for value in date_range(candidate["start"], candidate["end"]) if value not in covered)
    if len(by_owner) == 2 and by_owner["clement"] == by_owner["elsa"]:
        by_owner = {"both": by_owner["clement"]}
    return [dict(candidate, owner=owner, start=start, end=end)
            for owner, spans in by_owner.items() for start, end in spans]


def replace_base_locations(db, candidate, records):
    """Replace only the requested civil days, preserving surrounding periods.

    A stay with a booking checklist must be edited deliberately: splitting it
    would otherwise duplicate or lose its boarding / flight reservations.
    """
    for record in records:
        if record["kind"] != "location" or record.get("id") == candidate.get("id"):
            continue
        shared = people(candidate) & people(record)
        if not shared or candidate["start"] > record["end"] or record["start"] > candidate["end"]:
            continue
        if record["boarding_status"] != "not_needed" or record["transport_status"] != "not_needed":
            raise PlannerError("Cette période recoupe un séjour avec un suivi de réservation. Ouvrez ce séjour dans Déplacements pour ajuster ses dates avant d’ajouter le nouveau lieu.", 409)
        pieces = {}
        for person in people(record):
            spans = []
            if person not in shared:
                spans.append((record["start"], record["end"]))
            else:
                if record["start"] < candidate["start"]:
                    spans.append((record["start"], (day(candidate["start"]) - timedelta(days=1)).isoformat()))
                if record["end"] > candidate["end"]:
                    spans.append(((day(candidate["end"]) + timedelta(days=1)).isoformat(), record["end"]))
            for bounds in spans:
                pieces.setdefault(bounds, set()).add(person)
        db.execute("DELETE FROM planner_records WHERE id=?", (record["id"],))
        for index, ((start, end), owners) in enumerate(sorted(pieces.items())):
            piece = dict(record, start=start, end=end, owner="both" if len(owners) == 2 else next(iter(owners)))
            put_record(db, piece, record["id"] if index == 0 else None, record["revision"] + 1)


def coverage(records, year):
    days = {d: {"date": d, "clement": None, "elsa": None} for d in date_range(f"{year}-01-01", f"{year}-12-31")}
    for record in records:
        if record["kind"] != "location":
            continue
        for value in date_range(max(record["start"], f"{year}-01-01"), min(record["end"], f"{year}-12-31")):
            for person in people(record):
                days[value][person] = {"id": record["id"], "title": record["title"], "place": record["place"]}
    missing = []
    for owner in ("both", "clement", "elsa"):
        matching = []
        for value, row in days.items():
            absent = {p for p in ("clement", "elsa") if row[p] is None}
            if absent == ({"clement", "elsa"} if owner == "both" else {owner}):
                matching.append(value)
        missing.extend({"owner": owner, "start": start, "end": end, "count": (day(end) - day(start)).days + 1}
                       for start, end in ranges(matching))
    missing_count = sum(1 for row in days.values() if row["clement"] is None or row["elsa"] is None)
    return {"days": list(days.values()), "missing": sorted(missing, key=lambda r: (r["start"], r["owner"])),
            "missing_days": missing_count, "covered_days": len(days) - missing_count, "total_days": len(days)}


def reservations(records):
    result, alerts = [], []
    for r in records:
        if r["kind"] in {"boarding", "transport"}:
            result.append(r)
            if r["status"] in {"pending", "needs_change"}:
                alerts.append({"record_id": r["id"], "start": r["start"], "end": r["end"], "kind": r["kind"], "title": r["title"] + " : " + STATUS_LABELS[r["status"]].lower()})
        if r["kind"] != "location":
            continue
        for kind in ("boarding", "transport"):
            status = r[kind + "_status"]
            if status == "not_needed":
                continue
            title = ("Pension chien" if kind == "boarding" else "Transport") + " · " + r["title"]
            base = {"id": r["id"] + ":" + kind, "record_id": r["id"], "kind": kind,
                    "title": title, "owner": r["owner"], "status": status,
                    "notes": r.get(kind + "_notes", ""), "linked": True, "stay": r["title"]}
            start = r.get(kind + "_start") or r["start"]
            end = r.get(kind + "_end") or r["end"]
            if kind == "boarding":
                result.append(dict(base, start=start, end=end))
            else:
                result.append(dict(base, title="Aller · " + (r.get("transport_origin", "") + " → " if r.get("transport_origin") else "") + r["title"], start=start, end=start, direction="outbound",
                                   mode=r.get("transport_mode", ""), origin=r.get("transport_origin", ""), destination=r["title"]))
                if r.get("transport_round_trip") is not False:
                    return_status = "pending" if status == "booked" and not r.get("transport_end") else status
                    result.append(dict(base, id=base["id"] + ":return", title="Retour · " + r["title"] + (" → " + r["transport_origin"] if r.get("transport_origin") else ""), start=end, end=end, direction="return", status=return_status,
                                       estimated_date=not bool(r.get("transport_end")),
                                       mode=r.get("transport_mode", ""), origin=r["title"], destination=r.get("transport_origin", "")))
                    if return_status == "pending" and status == "booked":
                        alerts.append({"record_id": r["id"], "start": end, "end": end, "kind": kind, "title": "Retour de " + r["title"] + " : réservation et date à confirmer"})
            if status in {"pending", "needs_change"}:
                alerts.append({"record_id": r["id"], "start": r["start"], "end": r["end"], "kind": kind, "title": title + " : " + STATUS_LABELS[status].lower()})
            elif kind == "boarding" and (start > r["start"] or end < r["end"]):
                alerts.append({"record_id": r["id"], "start": r["start"], "end": r["end"], "kind": kind, "title": "Pension : dates à vérifier pour " + r["title"]})
    return result, sorted(alerts, key=lambda a: a["start"])


def training_events(sessions, modality_range):
    def normalize(value):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(value), fmt).date().isoformat()
            except (ValueError, TypeError):
                pass
        return None
    result = []
    for s in sessions:
        if not isinstance(s, dict) or not s.get("id") or s.get("cancelled") or s.get("canceled") or s.get("status") in {"cancelled", "canceled", "annulee"}:
            continue
        presencial = modality_range(s, "presentiel")
        presentiel = (presencial or {}).get("start") or s.get("date_presentiel_debut") or s.get("despPresentielStart")
        # Only infer an on-site start for a course explicitly known to be on site.
        if not presentiel and (s.get("apsPlanningMode") == "full_presentiel" or str(s.get("formation", "")).upper() in {"SSIAP1", "SSIAP2", "SSIAP3", "SST"}):
            presentiel = s.get("date_debut")
        for key, label, value in (("training_start", "Début formation", s.get("date_debut")),
                                  ("training_onsite", "Début présentiel", presentiel),
                                  ("training_end", "Fin formation", s.get("date_fin")),
                                  ("training_exam", "Examen", s.get("date_exam"))):
            value = normalize(value)
            if value:
                result.append({"id": "session:" + str(s["id"]) + ":" + key, "kind": key,
                               "title": str(s.get("formation") or "Formation") + " · " + label,
                               "formation": str(s.get("formation") or ""),
                               "ssiap": "SSIAP" in str(s.get("formation") or "").upper(),
                               "start": value, "end": value, "owner": "both", "readonly": True,
                               "url": "/sessions/" + quote(str(s["id"]), safe=""),
                               "notes": str(s.get("dirigeant_location_label") or s.get("salle") or s.get("room") or "")})
    return result


def register(app, data_dir, load_sessions, modality_range):
    bp = Blueprint("personal_planner", __name__, url_prefix="/gestion-clement-elsa")
    app.config.setdefault("PERSONAL_PLANNER_DB", os.path.join(data_dir, "personal_planner.sqlite3"))

    @bp.before_request
    def protect_mutations():
        # Authentication is enforced by the application's global admin guard.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            expected = session.get("planner_csrf", "")
            token = request.headers.get("X-Planner-CSRF", "")
            if not expected or not hmac.compare_digest(expected, token):
                return jsonify(error="Votre session a expiré. Rechargez la page."), 403
            if request.content_length and request.content_length > 100000:
                return jsonify(error="Le contenu est trop volumineux."), 413
            if not request.is_json:
                return jsonify(error="Format de requête invalide."), 400

    @bp.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.errorhandler(PlannerError)
    def validation_error(error):
        return jsonify(error=str(error)), error.status

    @bp.errorhandler(sqlite3.Error)
    @bp.errorhandler(OSError)
    def storage_error(error):
        current_app.logger.exception("PERSONAL_PLANNER_STORAGE_FAILED")
        return jsonify(error="Le planning est momentanément indisponible. Vos données sont conservées. Réessayez."), 503

    @bp.get("")
    @bp.get("/")
    def index():
        session.setdefault("planner_csrf", secrets.token_urlsafe(32))
        return render_template("personal_planner.html", planner_csrf=session["planner_csrf"])

    @bp.get("/data")
    def data():
        try:
            year = int(request.args.get("year", date.today().year))
        except ValueError:
            raise PlannerError("Année invalide.") from None
        if not 2000 <= year <= 2100:
            raise PlannerError("Année invalide.")
        with closing(connect(current_app.config["PERSONAL_PLANNER_DB"])) as db:
            records = read_records(db)
        training_error = None
        try:
            training = training_events(load_sessions().get("sessions", []), modality_range)
        except Exception:
            current_app.logger.exception("PERSONAL_PLANNER_TRAINING_READ_FAILED")
            training = []
            training_error = "Les dates de formation sont temporairement indisponibles. Votre planning personnel reste accessible."
        bookings, alerts = reservations(records)
        return jsonify(records=records, training=training, training_error=training_error,
                       reservations=bookings, alerts=alerts, coverage=coverage(records, year), year=year,
                       today=date.today().isoformat())

    @bp.get("/month.pdf")
    def month_pdf():
        from services.personal_planner_pdf import render_month
        try:
            year = int(request.args.get("year", date.today().year))
            month = int(request.args.get("month", date.today().month))
        except ValueError:
            raise PlannerError("Mois ou année invalide.") from None
        if not 2000 <= year <= 2100 or not 1 <= month <= 12:
            raise PlannerError("Mois ou année invalide.")
        owner = request.args.get("owner", "all")
        if owner not in OWNERS | {"all"}:
            raise PlannerError("Personne invalide.")
        hidden = request.args.get("hidden", "").split(",")
        hidden = {key for key in hidden if key in KINDS | {"ssiap", "training_start", "training_onsite", "training_end", "training_exam"}}
        with closing(connect(current_app.config["PERSONAL_PLANNER_DB"])) as db:
            records = read_records(db)
        try:
            training = training_events(load_sessions().get("sessions", []), modality_range)
        except Exception:
            current_app.logger.exception("PERSONAL_PLANNER_PDF_TRAINING_FAILED")
            raise PlannerError("Export indisponible : les dates de formation ne peuvent pas être chargées. Réessayez pour obtenir un planning complet.", 503) from None
        bookings, _ = reservations(records)
        document = render_month(records, training, bookings, coverage(records, year)["days"], year, month, owner, hidden)
        return send_file(BytesIO(document), mimetype="application/pdf", as_attachment=False,
                         download_name=f"planning-clement-elsa-{year}-{month:02d}.pdf", max_age=0)

    @bp.post("/records")
    def create():
        payload = request.get_json(silent=True)
        record = validate(payload)
        repeated = payload.get("repeat", "none")
        if not isinstance(repeated, str) or repeated not in {"none", "weekly", "fortnightly"}:
            raise PlannerError("Répétition invalide.")
        candidates = [record]
        if repeated != "none":
            if record["kind"] != "louise":
                raise PlannerError("La répétition est disponible pour les périodes avec Louise.")
            until = day(payload.get("repeat_until"), "Fin de répétition")
            start, end = day(record["start"]), day(record["end"])
            step = 7 if repeated == "weekly" else 14
            if until < end or (until - start).days > 1096 or (end - start).days >= step:
                raise PlannerError("Vérifiez la fin de répétition et la durée de chaque période (sans chevauchement, trois ans maximum).")
            group = uuid.uuid4().hex
            candidates = []
            while start <= until:
                candidates.append(dict(record, start=start.isoformat(), end=min(end, until).isoformat(), series_id=group))
                start += timedelta(days=step)
                end += timedelta(days=step)
        with closing(connect(current_app.config["PERSONAL_PLANNER_DB"])) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = read_records(db)
            if record["kind"] == "location":
                if payload.get("fill_gaps") is True and payload.get("replace_conflicts") is True:
                    raise PlannerError("Choisissez soit le remplissage des jours manquants, soit le remplacement du lieu habituel.")
                if payload.get("fill_gaps") is True:
                    # Gap filling is for a base location, not for copying bookings
                    # onto several disconnected stays.
                    if record["boarding_status"] != "not_needed" or record["transport_status"] != "not_needed":
                        raise PlannerError("Pour remplir les jours sans lieu, indiquez « Pas nécessaire » pour les réservations. Ajoutez les séjours à réserver séparément.")
                    candidates = fill_locations(record, existing)
                elif payload.get("replace_conflicts") is True:
                    replace_base_locations(db, record, existing)
                else:
                    location_overlap(record, existing)
            ids = [put_record(db, r) for r in candidates]
        return jsonify(ids=ids, count=len(ids)), 201

    @bp.route("/records/<record_id>", methods=["PUT", "DELETE"])
    def edit(record_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise PlannerError("Requête invalide.")
        with closing(connect(current_app.config["PERSONAL_PLANNER_DB"])) as db, db:
            db.execute("BEGIN IMMEDIATE")
            records = read_records(db)
            record = next((r for r in records if r["id"] == record_id), None)
            if not record:
                raise PlannerError("Cet élément a déjà été supprimé. Actualisez le planning.", 404)
            if type(payload.get("revision")) is not int or payload["revision"] != record["revision"]:
                raise PlannerError("Cet élément a été modifié sur un autre appareil. Fermez ce formulaire et actualisez le planning avant de réessayer.", 409)
            if request.method == "DELETE":
                ids = [record_id]
                if payload.get("delete_series") is True and record.get("series_id"):
                    ids = [r["id"] for r in records if r.get("series_id") == record["series_id"]]
                db.executemany("DELETE FROM planner_records WHERE id=?", [(rid,) for rid in ids])
                return jsonify(count=len(ids))
            replacement = validate(payload)
            if replacement["kind"] != record["kind"]:
                raise PlannerError("La catégorie ne peut pas être changée après la création.")
            if replacement["kind"] == "location":
                if payload.get("replace_conflicts") is True:
                    replace_base_locations(db, dict(replacement, id=record_id), records)
                else:
                    location_overlap(dict(replacement, id=record_id), records)
            if record.get("series_id"):
                replacement["series_id"] = record["series_id"]
            put_record(db, replacement, record_id, record["revision"] + 1)
        return jsonify(id=record_id)

    app.register_blueprint(bp)
