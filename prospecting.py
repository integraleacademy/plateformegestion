"""Prospection commerciale des organismes de formation sécurité."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

logger = logging.getLogger(__name__)

prospecting_bp = Blueprint("prospecting", __name__)

KEYWORDS = (
    "sécurité", "securite", "sûreté", "surete", "protection", "aps", "ssiap",
    "agent de sécurité", "agent de securite", "vidéoprotection", "videoprotection",
    "formation sécurité", "formation securite", "centre de formation",
)
STATUSES = ("Nouveau", "À qualifier", "À contacter", "Contacté", "À relancer", "Converti", "Non pertinent")
DATA_GOUV_DATASET = "liste-publique-des-organismes-de-formation-l-6351-7-1-du-code-du-travail"
DATA_GOUV_API = f"https://www.data.gouv.fr/api/1/datasets/{DATA_GOUV_DATASET}/"
RNE_SEARCH_API = "https://recherche-entreprises.api.gouv.fr/search"

FIELD_ALIASES = {
    "name": ("nom", "denomination", "raison_sociale", "raison sociale", "nom_organisme", "name"),
    "siren": ("siren", "numero_siren"),
    "siret": ("siret", "numero_siret", "siret_etablissement_declarant"),
    "city": ("ville", "commune", "libelle_commune", "adresse_ville"),
    "postal_code": ("code_postal", "code postal", "cp", "adresse_code_postal"),
    "email": ("email", "courriel", "adresse_electronique"),
    "phone": ("telephone", "téléphone", "tel"),
    "website": ("site_internet", "site internet", "url", "website"),
    "manager": ("dirigeant", "representant_legal", "nom_representant"),
    "ape": ("code_ape", "ape", "activite_principale", "naf"),
    "created_at": ("date_creation", "date de creation", "date_creation_entreprise"),
    "nda": ("numero_de_declaration_d_activite", "numero declaration activite", "nda"),
    "qualiopi": ("qualiopi", "certifications", "certification_qualite", "certifie_qualite"),
}


def _db_path() -> Path:
    root = os.environ.get("PERSIST_DIR") or os.environ.get("DATA_DIR") or current_app.root_path
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path / "prospects.db"


def get_prospect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(_db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def init_prospect_db() -> None:
    with get_prospect_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
                score INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                siren TEXT DEFAULT '',
                siret TEXT DEFAULT '',
                city TEXT DEFAULT '',
                department TEXT DEFAULT '',
                manager TEXT DEFAULT '',
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                website TEXT DEFAULT '',
                source TEXT NOT NULL,
                source_url TEXT DEFAULT '',
                signal TEXT DEFAULT '',
                commercial_status TEXT NOT NULL DEFAULT 'Nouveau',
                comment TEXT DEFAULT '',
                detected_at TEXT NOT NULL,
                company_created_at TEXT DEFAULT '',
                ape_code TEXT DEFAULT '',
                qualiopi INTEGER NOT NULL DEFAULT 0,
                nda TEXT DEFAULT '',
                ai_analysis TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_prospects_score ON prospects(score DESC);
            CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(commercial_status);
            CREATE INDEX IF NOT EXISTS idx_prospects_detected ON prospects(detected_at DESC);
            CREATE TABLE IF NOT EXISTS prospect_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                sources TEXT DEFAULT '',
                found_count INTEGER NOT NULL DEFAULT 0,
                added_count INTEGER NOT NULL DEFAULT 0,
                updated_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT DEFAULT ''
            );
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _normalized_key(value: str) -> str:
    value = _clean(value).lower().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _row_value(row: dict, field: str) -> str:
    normalized = {_normalized_key(key): value for key, value in row.items()}
    for alias in FIELD_ALIASES[field]:
        value = normalized.get(_normalized_key(alias))
        if value not in (None, ""):
            return _clean(value)
    return ""


def _department(postal_code: str) -> str:
    digits = re.sub(r"\D", "", postal_code)
    if len(digits) < 2:
        return ""
    if digits.startswith(("97", "98")) and len(digits) >= 3:
        return digits[:3]
    return digits[:2]


def _parse_date(value: str) -> date | None:
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            continue
    return None


def _is_truthy(value: str) -> bool:
    lowered = _clean(value).lower()
    return lowered in {"1", "true", "oui", "yes", "certifié", "certifie", "qualiopi"} or "qualiopi" in lowered


def score_prospect(prospect: dict) -> tuple[int, str]:
    """Retourne un score commercial explicable, borné entre 0 et 100."""
    haystack = " ".join((prospect.get("name", ""), prospect.get("signal", ""))).lower()
    matched = sorted({keyword for keyword in KEYWORDS if keyword in haystack})
    score = 10
    reasons = []
    if prospect.get("ape_code", "").replace(".", "").upper() == "8559A":
        score += 30
        reasons.append("APE 8559A")
    if matched:
        keyword_points = min(30, 10 + (len(matched) - 1) * 5)
        score += keyword_points
        reasons.append("mots-clés : " + ", ".join(matched[:3]))
    created = _parse_date(prospect.get("company_created_at", ""))
    if created:
        age = (date.today() - created).days
        if age <= 90:
            score += 20
            reasons.append("création < 3 mois")
        elif age <= 365:
            score += 12
            reasons.append("création < 1 an")
        elif age <= 730:
            score += 5
            reasons.append("création < 2 ans")
    if prospect.get("qualiopi"):
        score += 15
        reasons.append("Qualiopi")
    contact_points = 0
    if prospect.get("email"):
        contact_points += 5
    if prospect.get("phone"):
        contact_points += 3
    if prospect.get("website"):
        contact_points += 2
    score += contact_points
    if contact_points:
        reasons.append("coordonnées disponibles")
    return min(score, 100), " · ".join(reasons) or "Organisme de formation détecté"


def _candidate(raw: dict, source: str, source_url: str = "") -> dict:
    postal_code = _row_value(raw, "postal_code")
    prospect = {
        "name": _row_value(raw, "name") or "Organisme sans dénomination",
        "siren": re.sub(r"\D", "", _row_value(raw, "siren")),
        "siret": re.sub(r"\D", "", _row_value(raw, "siret")),
        "city": _row_value(raw, "city"),
        "department": _department(postal_code),
        "manager": _row_value(raw, "manager"),
        "email": _row_value(raw, "email"),
        "phone": _row_value(raw, "phone"),
        "website": _row_value(raw, "website"),
        "source": source,
        "source_url": source_url,
        "signal": _clean(raw.get("signal")) or "Présence dans une source officielle de formation",
        "company_created_at": _row_value(raw, "created_at"),
        "ape_code": _row_value(raw, "ape"),
        "qualiopi": _is_truthy(_row_value(raw, "qualiopi")),
        "nda": _row_value(raw, "nda"),
    }
    score, explanation = score_prospect(prospect)
    prospect["score"] = score
    prospect["signal"] = explanation
    identity = prospect["siret"] or prospect["siren"] or f'{prospect["name"]}|{prospect["city"]}'
    prospect["fingerprint"] = hashlib.sha256(identity.lower().encode("utf-8")).hexdigest()
    return prospect


def _request_json(url: str, *, headers: dict | None = None, timeout: int = 25) -> dict:
    request_object = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "IntegraleAcademyProspector/1.0", **(headers or {})},
    )
    with urllib.request.urlopen(request_object, timeout=timeout) as response:
        return json.loads(response.read().decode(response.headers.get_content_charset() or "utf-8"))


def _download(url: str, max_bytes: int = 60 * 1024 * 1024) -> bytes:
    request_object = urllib.request.Request(url, headers={"User-Agent": "IntegraleAcademyProspector/1.0"})
    with urllib.request.urlopen(request_object, timeout=45) as response:
        content = response.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError("La ressource dépasse la taille maximale autorisée (60 Mo).")
    return content


def _data_gouv_rows(limit: int) -> list[dict]:
    metadata = _request_json(DATA_GOUV_API)
    resources = metadata.get("resources") or []
    candidates = [r for r in resources if (r.get("format") or "").lower() in {"csv", "xlsx", "xls"}]
    if not candidates:
        raise ValueError("Aucune ressource CSV/XLSX trouvée sur data.gouv.fr.")
    preferred = [resource for resource in candidates if (resource.get("format") or "").lower() == "csv"] or candidates
    resource = max(preferred, key=lambda resource: resource.get("last_modified") or resource.get("created_at") or "")
    content = _download(resource.get("latest") or resource.get("url"))
    fmt = (resource.get("format") or "").lower()
    rows = []
    if fmt == "csv":
        text = content.decode("utf-8-sig", errors="replace")
        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        for row in reader:
            candidate = _candidate(row, "data.gouv / DGEFP", resource.get("url", ""))
            haystack = f'{candidate["name"]} {candidate["signal"]}'.lower()
            if candidate["ape_code"].replace(".", "").upper() == "8559A" or any(keyword in haystack for keyword in KEYWORDS):
                rows.append(candidate)
            if len(rows) >= limit:
                break
    else:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        headers = [_clean(value) for value in next(iterator)]
        for values in iterator:
            candidate = _candidate(dict(zip(headers, values)), "data.gouv / DGEFP", resource.get("url", ""))
            haystack = f'{candidate["name"]} {candidate["signal"]}'.lower()
            if candidate["ape_code"].replace(".", "").upper() == "8559A" or any(keyword in haystack for keyword in KEYWORDS):
                rows.append(candidate)
            if len(rows) >= limit:
                break
    return rows


def _rne_rows(limit: int) -> list[dict]:
    params = urllib.parse.urlencode({"activite_principale": "85.59A", "per_page": min(limit, 25), "page": 1})
    payload = _request_json(f"{RNE_SEARCH_API}?{params}")
    prospects = []
    for company in (payload.get("results") or [])[:limit]:
        headquarters = company.get("siege") or {}
        managers = company.get("dirigeants") or []
        raw = {
            "denomination": company.get("nom_complet") or company.get("nom_raison_sociale"),
            "siren": company.get("siren"),
            "siret": headquarters.get("siret"),
            "ville": headquarters.get("libelle_commune"),
            "code_postal": headquarters.get("code_postal"),
            "activite_principale": company.get("activite_principale"),
            "date_creation": company.get("date_creation"),
            "dirigeant": " ".join(_clean(managers[0].get(key)) for key in ("prenom", "nom") if managers) if managers else "",
            "signal": "Nouvelle entreprise APE 8559A repérée dans l’Annuaire des Entreprises / RNE",
        }
        prospects.append(_candidate(raw, "RNE / Annuaire des Entreprises", "https://annuaire-entreprises.data.gouv.fr"))
    return prospects


def _web_rows(limit: int) -> list[dict]:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return []
    body = json.dumps({"q": '"centre de formation" (sécurité OR SSIAP OR APS) France', "num": min(limit, 10)}).encode()
    request_object = urllib.request.Request(
        "https://google.serper.dev/search",
        data=body,
        headers={"Content-Type": "application/json", "X-API-KEY": api_key},
        method="POST",
    )
    with urllib.request.urlopen(request_object, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    prospects = []
    for item in payload.get("organic", [])[:limit]:
        raw = {
            "nom": item.get("title"),
            "site_internet": item.get("link"),
            "signal": item.get("snippet") or "Résultat web correspondant aux mots-clés sécurité",
        }
        candidate = _candidate(raw, "Recherche web", item.get("link", ""))
        haystack = f'{candidate["name"]} {raw["signal"]}'.lower()
        if any(keyword in haystack for keyword in KEYWORDS):
            prospects.append(candidate)
    return prospects


def _upsert(prospect: dict) -> bool:
    now = _now()
    values = (
        prospect["fingerprint"], prospect["score"], prospect["name"], prospect["siren"], prospect["siret"],
        prospect["city"], prospect["department"], prospect["manager"], prospect["email"], prospect["phone"],
        prospect["website"], prospect["source"], prospect["source_url"], prospect["signal"], now,
        prospect["company_created_at"], prospect["ape_code"], int(prospect["qualiopi"]), prospect["nda"], now,
    )
    with get_prospect_db() as connection:
        existing = connection.execute("SELECT id FROM prospects WHERE fingerprint = ?", (prospect["fingerprint"],)).fetchone()
        connection.execute(
            """INSERT INTO prospects (
                fingerprint, score, name, siren, siret, city, department, manager, email, phone, website,
                source, source_url, signal, detected_at, company_created_at, ape_code, qualiopi, nda, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                score=excluded.score, name=excluded.name, siren=excluded.siren, siret=excluded.siret,
                city=excluded.city, department=excluded.department,
                manager=CASE WHEN excluded.manager != '' THEN excluded.manager ELSE prospects.manager END,
                email=CASE WHEN excluded.email != '' THEN excluded.email ELSE prospects.email END,
                phone=CASE WHEN excluded.phone != '' THEN excluded.phone ELSE prospects.phone END,
                website=CASE WHEN excluded.website != '' THEN excluded.website ELSE prospects.website END,
                source=excluded.source, source_url=excluded.source_url, signal=excluded.signal,
                company_created_at=excluded.company_created_at, ape_code=excluded.ape_code,
                qualiopi=excluded.qualiopi, nda=excluded.nda, updated_at=excluded.updated_at
            """,
            values,
        )
    return existing is None


def run_scan() -> dict:
    init_prospect_db()
    limit = max(5, min(int(os.environ.get("PROSPECT_SCAN_LIMIT", "250")), 2000))
    with get_prospect_db() as connection:
        cursor = connection.execute(
            "INSERT INTO prospect_scans(started_at, status) VALUES (?, 'running')", (_now(),)
        )
        scan_id = cursor.lastrowid
    found = added = updated = 0
    sources = []
    errors = []
    scanners = (("data.gouv / DGEFP", _data_gouv_rows), ("RNE", _rne_rows), ("Web", _web_rows))
    for source_name, scanner in scanners:
        try:
            rows = scanner(limit)
            if rows or source_name != "Web":
                sources.append(source_name)
            for prospect in rows:
                found += 1
                if _upsert(prospect):
                    added += 1
                else:
                    updated += 1
        except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as exc:
            logger.warning("Échec du scanner %s: %s", source_name, exc)
            errors.append(f"{source_name}: {exc}")
    status = "success" if found else "partial" if errors else "success"
    with get_prospect_db() as connection:
        connection.execute(
            """UPDATE prospect_scans SET finished_at=?, status=?, sources=?, found_count=?, added_count=?,
               updated_count=?, error_message=? WHERE id=?""",
            (_now(), status, ", ".join(sources), found, added, updated, " | ".join(errors), scan_id),
        )
    return {"found": found, "added": added, "updated": updated, "errors": errors}


def _openai_mail(prospect: sqlite3.Row) -> str:
    fallback = (
        f"Objet : Échange entre acteurs de la formation sécurité\n\nBonjour,\n\n"
        f"Je me permets de vous contacter au sujet de {prospect['name']}, que nous avons identifié comme un acteur "
        f"de la formation sécurité à {prospect['city'] or 'votre région'}.\n\n"
        "Intégrale Academy accompagne les professionnels de la sécurité dans le développement de leurs formations. "
        "Je serais ravi d’échanger avec vous afin d’identifier de possibles synergies.\n\n"
        "Seriez-vous disponible pour un bref échange cette semaine ?\n\nBien cordialement,\nIntégrale Academy"
    )
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return fallback
    prompt = (
        "Rédige un email de prospection B2B en français, sobre, personnalisé, sans inventer d'information, "
        "avec un objet et moins de 170 mots. Appel à l'action: échange de 15 minutes.\n"
        f"Prospect: {prospect['name']}; ville: {prospect['city']}; APE: {prospect['ape_code']}; "
        f"Qualiopi: {'oui' if prospect['qualiopi'] else 'non vérifié'}; signal: {prospect['signal']}."
    )
    body = json.dumps({"model": os.environ.get("OPENAI_MODEL", "gpt-5-mini"), "input": prompt}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = _clean(payload.get("output_text"))
        if not text:
            parts = []
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        parts.append(content.get("text", ""))
            text = "\n".join(parts).strip()
        return text or fallback
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        logger.warning("Génération OpenAI indisponible: %s", exc)
        return fallback


@prospecting_bp.get("/prospection")
def prospecting_shortcut():
    """URL lisible pouvant être partagée avec l'équipe commerciale."""
    return redirect(url_for("prospecting.admin_prospects"))


@prospecting_bp.get("/admin")
def admin_prospects():
    init_prospect_db()
    search = _clean(request.args.get("q"))
    status = _clean(request.args.get("status"))
    minimum_score = request.args.get("score", type=int) or 0
    clauses = ["score >= ?"]
    parameters: list = [minimum_score]
    if search:
        clauses.append("(name LIKE ? OR siren LIKE ? OR siret LIKE ? OR city LIKE ? OR signal LIKE ?)")
        parameters.extend([f"%{search}%"] * 5)
    if status in STATUSES:
        clauses.append("commercial_status = ?")
        parameters.append(status)
    where = " AND ".join(clauses)
    with get_prospect_db() as connection:
        prospects = connection.execute(
            f"SELECT * FROM prospects WHERE {where} ORDER BY score DESC, detected_at DESC LIMIT 1000", parameters
        ).fetchall()
        stats = connection.execute(
            """SELECT COUNT(*) total, SUM(commercial_status='Nouveau') new_count,
               SUM(commercial_status='À relancer') followup_count,
               COALESCE(ROUND(AVG(score)), 0) average_score FROM prospects"""
        ).fetchone()
        last_scan = connection.execute("SELECT * FROM prospect_scans ORDER BY id DESC LIMIT 1").fetchone()
    return render_template(
        "admin_prospects.html", prospects=prospects, stats=stats, last_scan=last_scan,
        statuses=STATUSES, filters={"q": search, "status": status, "score": minimum_score},
        openai_enabled=bool(os.environ.get("OPENAI_API_KEY")), web_enabled=bool(os.environ.get("SERPER_API_KEY")),
    )


@prospecting_bp.route("/cron-prospects-scan", methods=["GET", "POST"])
def cron_scan_prospects():
    expected_secret = os.environ.get("CRON_SECRET")
    provided_secret = request.headers.get("Authorization", "").removeprefix("Bearer ") or request.args.get("key")
    if not expected_secret or provided_secret != expected_secret:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = run_scan()
    return jsonify({"ok": True, **result})


@prospecting_bp.post("/admin/scan")
def scan_prospects():
    result = run_scan()
    if result["found"]:
        flash(f"Scan terminé : {result['added']} nouveau(x), {result['updated']} actualisé(s).", "success")
    else:
        flash("Aucun prospect importé. Vérifiez l’accès réseau et les sources configurées.", "error")
    if result["errors"]:
        flash("Certaines sources sont indisponibles : " + " | ".join(result["errors"]), "warning")
    return redirect(url_for("prospecting.admin_prospects"))


@prospecting_bp.post("/admin/prospects/<int:prospect_id>/update")
def update_prospect(prospect_id: int):
    status = _clean(request.form.get("commercial_status"))
    if status not in STATUSES:
        status = "À qualifier"
    comment = _clean(request.form.get("comment"))
    with get_prospect_db() as connection:
        connection.execute(
            "UPDATE prospects SET commercial_status=?, comment=?, updated_at=? WHERE id=?",
            (status, comment, _now(), prospect_id),
        )
    flash("Prospect mis à jour.", "success")
    return redirect(url_for("prospecting.admin_prospects"))


@prospecting_bp.post("/admin/prospects/<int:prospect_id>/contacted")
def contact_prospect(prospect_id: int):
    with get_prospect_db() as connection:
        connection.execute(
            "UPDATE prospects SET commercial_status='Contacté', updated_at=? WHERE id=?", (_now(), prospect_id)
        )
    flash("Prospect marqué comme contacté.", "success")
    return redirect(url_for("prospecting.admin_prospects"))


@prospecting_bp.post("/admin/prospects/<int:prospect_id>/follow-up")
def follow_up_prospect(prospect_id: int):
    with get_prospect_db() as connection:
        connection.execute(
            "UPDATE prospects SET commercial_status='À relancer', updated_at=? WHERE id=?", (_now(), prospect_id)
        )
    flash("Prospect ajouté aux relances.", "success")
    return redirect(url_for("prospecting.admin_prospects"))


@prospecting_bp.post("/admin/prospects/<int:prospect_id>/delete")
def delete_prospect(prospect_id: int):
    with get_prospect_db() as connection:
        connection.execute("DELETE FROM prospects WHERE id=?", (prospect_id,))
    flash("Prospect supprimé.", "success")
    return redirect(url_for("prospecting.admin_prospects"))


@prospecting_bp.get("/admin/prospects/<int:prospect_id>/mail")
def prepare_mail(prospect_id: int):
    init_prospect_db()
    with get_prospect_db() as connection:
        prospect = connection.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not prospect:
        return Response("Prospect introuvable", status=404)
    return Response(_openai_mail(prospect), content_type="text/plain; charset=utf-8")


@prospecting_bp.get("/admin/export.xlsx")
def export_prospects():
    init_prospect_db()
    with get_prospect_db() as connection:
        prospects = connection.execute("SELECT * FROM prospects ORDER BY score DESC, detected_at DESC").fetchall()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Prospects sécurité"
    headers = ["Score", "Nom", "SIREN", "SIRET", "Ville", "Département", "Dirigeant", "Email", "Téléphone", "Site", "Source", "Signal", "Statut", "Commentaire", "Détection", "APE", "Qualiopi", "NDA"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="171717")
    for prospect in prospects:
        sheet.append([
            prospect["score"], prospect["name"], prospect["siren"], prospect["siret"], prospect["city"],
            prospect["department"], prospect["manager"], prospect["email"], prospect["phone"], prospect["website"],
            prospect["source"], prospect["signal"], prospect["commercial_status"], prospect["comment"],
            prospect["detected_at"], prospect["ape_code"], "Oui" if prospect["qualiopi"] else "Non vérifié", prospect["nda"],
        ])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    widths = (10, 35, 15, 18, 20, 14, 25, 30, 18, 30, 25, 50, 18, 35, 22, 12, 14, 18)
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[chr(64 + index)].width = width
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output, as_attachment=True, download_name=f"prospects-securite-{date.today().isoformat()}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
