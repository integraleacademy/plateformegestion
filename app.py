import os
import json
import uuid
import base64
import time
import tempfile
import zipfile
import hashlib
import smtplib
import urllib.parse
import urllib.request
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from email.mime.text import MIMEText
import logging
import threading

from flask import (
    Flask, render_template, request, redirect, url_for,
    abort, flash, send_file, send_from_directory, session, Response, jsonify
)
from werkzeug.utils import secure_filename



# --- 🔧 Forcer le fuseau horaire français ---
os.environ['TZ'] = 'Europe/Paris'
import time
time.tzset()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHORTCUTS_FILE = os.path.join(BASE_DIR, "data", "shortcuts.json")
SHORTCUT_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "shortcuts")
ALLOWED_SHORTCUT_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

logger = logging.getLogger("jury-notify")

from datetime import timedelta

IS_RENDER = os.environ.get("RENDER", "").lower() == "true"

# ✅ cookies/session persistants (Render = HTTPS)
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_RENDER,   # ✅ Secure seulement sur Render
)



ADMIN_USER = os.environ.get("ADMIN_USER")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


def ensure_shortcuts_storage():
    os.makedirs(os.path.dirname(SHORTCUTS_FILE), exist_ok=True)
    os.makedirs(SHORTCUT_UPLOAD_DIR, exist_ok=True)
    if not os.path.exists(SHORTCUTS_FILE):
        with open(SHORTCUTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_shortcuts():
    ensure_shortcuts_storage()
    try:
        with open(SHORTCUTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_shortcuts(shortcuts):
    ensure_shortcuts_storage()
    with open(SHORTCUTS_FILE, "w", encoding="utf-8") as f:
        json.dump(shortcuts, f, ensure_ascii=False, indent=2)


def allowed_shortcut_image(filename):
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_SHORTCUT_IMAGE_EXTENSIONS

# ------------------------------------------------------------
# 🔐 AUTHENTIFICATION ADMIN
# ------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):

        # ✅ Autoriser le lien formateur public avec token
        if request.path.startswith("/formateurs/") and "/upload" in request.path:
            return f(*args, **kwargs)

        # 🔐 Vérification session admin
        if not session.get("admin_logged"):
            return redirect(url_for("login", next=request.path))

        return f(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if email == ADMIN_USER and password == ADMIN_PASSWORD:
            session.permanent = True        # ✅ garde la session X jours
            session["admin_logged"] = True
            return redirect(request.args.get("next") or url_for("index"))


        flash("Identifiants incorrects", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.before_request
def protect_all_routes():
    path = request.path

    # ✅ autoriser page login / logout
    if path.startswith("/login") or path.startswith("/logout"):
        return None

    # ✅ autoriser les fichiers statiques (css/js/images)
    if path.startswith("/static/"):
        return None

    # ✅ autoriser les webhooks (Salesforce, etc.)
    if path.startswith("/webhooks/"):
        return None

    # ✅ autoriser lien public formateur (upload avec token)
    if path.startswith("/formateurs/") and "/upload" in path:
        return None

    # ✅ autoriser réponses jury (lien email)
    if path.startswith("/jury-response/"):
        return None

    # ✅ autoriser accès préfecture (auth basic gérée dans la route)
    if path.startswith("/prefecture/"):
        return None

    # ✅ autoriser les routes cron (Render Cron)
    if path.startswith("/cron-"):
        return None

    # ✅ autoriser routes publiques utiles (dashboard / tests)
    if path in ("/healthz", "/data.json", "/dotations_data.json", "/formateurs_data.json", "/tz-test"):
        return None

    # 🔐 tout le reste nécessite une session admin
    if not session.get("admin_logged"):
        return redirect(url_for("login", next=path))

    return None









# --- Filtres Jinja ---
def format_date(value):
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return value
app.jinja_env.filters['datefr'] = format_date

def to_datetime(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.now()
app.jinja_env.filters['datetime'] = to_datetime

# --- Helper utilisable dans Jinja ---
def get_status_label(step_index, session):
    """Renvoie un dict {status, deadline} lisible dans Jinja"""
    status, dl = status_for_step(step_index, session)
    return {"status": status, "deadline": dl}

app.jinja_env.globals['get_status_label'] = get_status_label


# --- Persistance ---
DATA_DIR = os.environ.get("DATA_DIR", "/mnt/data")
os.makedirs(DATA_DIR, exist_ok=True)
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
PRICE_ADAPTATOR_FILE = os.path.join(DATA_DIR, "price_adaptator.json")

PRICE_ADAPTATOR_DEFAULT_DISCOUNT = 30
PRICE_ADAPTATOR_FOLLOWUP_DAYS = 21
PRICE_ADAPTATOR_FORMATION_PRICES = {
    "APS": 1650,
    "A3P": 4200,
    "Dirigeant": 4300,
}
PRICE_ADAPTATOR_FORMATION_LABELS = {
    "APS": "Agent de prévention et de sécurité (APS)",
    "A3P": "Agent de protection physique des personnes (A3P)",
    "Dirigeant": "Dirigeant d'entreprise de sécurité privée (DESP)",
}
PRICE_ADAPTATOR_ALLOWED_FORMATIONS = {
    "APS": "APS",
    "A3P": "A3P",
    "DIRIGEANT": "Dirigeant",
}

# -----------------------
# 📅 Planning PDF (par session)
# -----------------------
PLANNING_DIR = os.path.join(DATA_DIR, "plannings")
os.makedirs(PLANNING_DIR, exist_ok=True)

def get_planning_for_session(sid):
    data = load_sessions()
    s = find_session(data, sid)
    if not s:
        return None
    return s.get("planning_pdf")  # ex: "planning_session_<sid>.pdf"

def set_planning_for_session(sid, filename):
    data = load_sessions()
    s = find_session(data, sid)
    if not s:
        return False
    s["planning_pdf"] = filename
    save_sessions(data)
    return True


FROM_EMAIL = os.environ.get("FROM_EMAIL")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

BREVO_SMTP_LOGIN = os.environ.get("BREVO_SMTP_LOGIN") or os.environ.get("BREVO_SMTP_USER")
BREVO_SMTP_KEY = os.environ.get("BREVO_SMTP_KEY")
BREVO_SMTP_SERVER = os.environ.get("BREVO_SMTP_SERVER", "smtp-relay.brevo.com")
BREVO_SMTP_PORT = int(os.environ.get("BREVO_SMTP_PORT", "587"))
BREVO_FROM_EMAIL = os.environ.get("BREVO_FROM_EMAIL")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SMS_SENDER = os.environ.get("BREVO_SMS_SENDER")

# -----------------------
# Utils persistance
# -----------------------
def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("sessions", [])
                    data.setdefault("jurys", [])
                    return data
        except Exception:
            pass
    return {"sessions": [], "jurys": []}

def save_sessions(data):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_price_adaptator_data():
    if os.path.exists(PRICE_ADAPTATOR_FILE):
        try:
            with open(PRICE_ADAPTATOR_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("prospects", [])
                    data.setdefault("dates", {})
                    return data
        except Exception:
            pass
    return {"prospects": [], "dates": {}}

def save_price_adaptator_data(data):
    with open(PRICE_ADAPTATOR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_price_adaptator_discount(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return PRICE_ADAPTATOR_DEFAULT_DISCOUNT
    return max(0, min(parsed, 100))

def normalize_price_adaptator_nom(value):
    if value is None:
        return ""
    return str(value).strip().upper()


def normalize_price_adaptator_prenom(value):
    if value is None:
        return ""
    cleaned = " ".join(str(value).strip().split())
    return cleaned.lower().title()


def normalize_price_adaptator_formation(value):
    if value is None:
        return None
    cleaned = str(value).strip().upper()
    return PRICE_ADAPTATOR_ALLOWED_FORMATIONS.get(cleaned)


def normalize_price_adaptator_proposed_price(price_value):
    try:
        return max(float(price_value), 0.0)
    except (TypeError, ValueError):
        return 0.0

def get_price_adaptator_followup_date(dates, formation):
    date_range = (dates or {}).get(formation, {})
    start_value = (date_range or {}).get("start")
    if not start_value:
        return None
    try:
        start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return start_date - timedelta(days=PRICE_ADAPTATOR_FOLLOWUP_DAYS)

def format_price_adaptator_date_range(date_range):
    if not date_range:
        return "dates à définir"
    start_value = date_range.get("start")
    end_value = date_range.get("end")
    try:
        start_label = datetime.strptime(start_value, "%Y-%m-%d").strftime("%d/%m/%Y") if start_value else None
    except ValueError:
        start_label = None
    try:
        end_label = datetime.strptime(end_value, "%Y-%m-%d").strftime("%d/%m/%Y") if end_value else None
    except ValueError:
        end_label = None
    if start_label and end_label:
        return f"{start_label} au {end_label}"
    if start_label:
        return start_label
    return "dates à définir"

def build_price_adaptator_message(prospect, dates, price_override=None):
    formation = prospect.get("formation", "")
    formation_full = PRICE_ADAPTATOR_FORMATION_LABELS.get(formation, formation)
    base_price = PRICE_ADAPTATOR_FORMATION_PRICES.get(formation, 0)
    discount_value = normalize_price_adaptator_discount((dates or {}).get(formation, {}).get("discount"))
    discounted_price = round(base_price * (1 - discount_value / 100))
    price_value = price_override if price_override is not None else discounted_price
    if base_price and price_value is not None:
        computed_discount = round((1 - price_value / base_price) * 100)
        discount_value = max(0, min(computed_discount, 100))
    price_label = f"{price_value:,.0f} €".replace(",", " ")
    base_price_label = f"{base_price:,.0f} €".replace(",", " ") if base_price else None
    date_text = format_price_adaptator_date_range((dates or {}).get(formation))
    prenom = normalize_price_adaptator_prenom(prospect.get("prenom"))
    logo_path = os.path.join("static", "img", "logo-integrale.png")
    logo_src = url_for("static", filename="img/logo-integrale.png", _external=True)
    try:
        with open(logo_path, "rb") as logo_file:
            logo_src = "data:image/png;base64," + base64.b64encode(logo_file.read()).decode("utf-8")
    except OSError:
        pass
    html = f"""
    <div style="font-family:'Segoe UI',Arial,Helvetica,sans-serif;background:#f2f4f7;padding:24px;">
      <style>
        @media screen and (max-width: 600px) {{
          .stack-column {{
            display: block !important;
            width: 100% !important;
            box-sizing: border-box !important;
          }}
          .stack-column-right {{
            text-align: left !important;
            padding-top: 0 !important;
          }}
          .email-container {{
            max-width: 100% !important;
            width: 100% !important;
          }}
          .email-body {{
            padding-left: 20px !important;
            padding-right: 20px !important;
          }}
        }}
      </style>
      <table role="presentation" cellspacing="0" cellpadding="0" class="email-container" style="width:100%;max-width:620px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e6e9ef;box-shadow:0 12px 30px rgba(16,24,40,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#111827,#1f2937);padding:24px;text-align:center;">
            <img src="{logo_src}" alt="Intégrale Academy" style="max-width:150px;height:auto;">
            <div style="margin-top:12px;color:#e5e7eb;font-size:14px;letter-spacing:0.4px;text-transform:uppercase;">Offre dernière minute</div>
          </td>
        </tr>
        <tr>
          <td class="email-body" style="padding:28px 32px 10px;color:#1f2937;line-height:1.7;">
            <p style="margin:0 0 16px;font-size:16px;">Bonjour {prenom},</p>
            <p style="margin:0 0 16px;font-size:16px;">
              Je me permets de revenir vers vous concernant notre formation <strong>{formation_full}</strong>.
            </p>
            <p style="margin:0 0 16px;font-size:16px;">
              Bonne nouvelle : Suite à des désistements, nous pouvons vous proposer un tarif exceptionnel de dernière
              minute à <strong>{price_label}</strong> au lieu de <strong>{base_price_label or "prix initial"}</strong> (prix initial de
              la formation), soit une remise de <strong>{discount_value:.0f} %</strong> pour notre prochaine session
              qui se déroulera du <strong>{date_text}</strong>.
            </p>
            <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;background:#f9fafb;border-radius:12px;border:1px solid #eef2f6;margin:16px 0;">
              <tr>
                <td class="stack-column" style="padding:18px 20px;">
                  <div style="font-size:14px;text-transform:uppercase;letter-spacing:0.8px;color:#6b7280;margin-bottom:8px;">Tarif exceptionnel</div>
                  <div style="font-size:28px;font-weight:700;color:#111827;">{price_label}</div>
                  <div style="font-size:14px;color:#6b7280;margin-top:4px;">
                    {f"Au lieu de {base_price_label} • remise de {discount_value:.0f} %" if base_price_label else "Offre dernière minute limitée"}
                  </div>
                </td>
                <td class="stack-column stack-column-right" style="padding:18px 20px;text-align:right;">
                  <div style="font-size:13px;color:#6b7280;text-transform:uppercase;letter-spacing:0.6px;">Prochaine session</div>
                  <div style="font-size:16px;font-weight:600;color:#111827;">{date_text}</div>
                </td>
              </tr>
            </table>
            <p style="margin:0 0 16px;font-size:16px;">
              Pour bénéficier de ce tarif et pour vous inscrire, nous vous remercions de bien vouloir nous contacter au
              <strong>04 22 47 07 68</strong>.
            </p>
            <p style="margin:0 0 20px;font-size:16px;">Cette offre est limitée, profitez-en dès maintenant.</p>
            <p style="margin:0 0 8px;font-size:16px;">
              Je reste à votre disposition pour tous renseignements complémentaires et je vous souhaite une bonne journée,
            </p>
            <p style="margin:0 0 0;font-size:16px;">A très bientôt !</p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 32px 28px;">
            <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;background:#111827;border-radius:12px;">
              <tr>
                <td style="padding:16px 20px;color:#ffffff;font-size:15px;">
                  <div style="font-weight:600;">Clément VAILLANT</div>
                  <div style="font-size:13px;color:#d1d5db;">Intégrale Academy</div>
                </td>
                <td style="padding:16px 20px;text-align:right;">
                  <span style="display:inline-block;background:#f9fafb;color:#111827;font-weight:600;padding:10px 16px;border-radius:999px;font-size:13px;">
                    04 22 47 07 68
                  </span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </div>
    """
    subject = f"Proposition tarif dernière minute {formation_full}"
    sms_message = (
        f"Bonjour {prenom}, Tarif exceptionnel dernière minute à {price_label} pour la formation "
        f"{formation_full} (du {date_text}). Offre limitée: contactez-nous au 04 22 47 07 68. "
        "Cordialement, Clément VAILLANT - Intégrale Academy"
    )
    return {
        "subject": subject,
        "html": html,
        "sms": sms_message,
        "price": price_value,
        "base_price": base_price,
        "discount_value": discount_value,
        "date_text": date_text,
    }

def attempt_price_adaptator_send(prospect, dates, price_override=None):
    message = build_price_adaptator_message(prospect, dates, price_override=price_override)
    email_sent = False
    email_error = None
    sms_sent = False
    sms_error = None
    email = (prospect.get("email") or "").strip()
    phone = (prospect.get("telephone") or "").strip()
    if email:
        email_sent, email_error = send_price_adaptator_email(email, message["subject"], message["html"])
    if phone:
        sms_sent, sms_error = send_price_adaptator_sms(phone, message["sms"])
    return {
        "email_sent": email_sent,
        "sms_sent": sms_sent,
        "email_error": email_error,
        "sms_error": sms_error,
        "price": message["price"],
    }

def process_price_adaptator_followups():
    data = load_price_adaptator_data()
    today = datetime.now().date()
    updated = False
    for prospect in data.get("prospects", []):
        if prospect.get("sent") or prospect.get("manual_sent"):
            continue
        followup_date = get_price_adaptator_followup_date(data.get("dates"), prospect.get("formation"))
        if not followup_date or followup_date > today:
            continue
        price_override = prospect.get("proposed_price")
        with app.app_context():
            result = attempt_price_adaptator_send(prospect, data.get("dates"), price_override=price_override)
        prospect["last_attempt_at"] = datetime.now().isoformat()
        prospect["last_error"] = result["email_error"] or result["sms_error"]
        prospect["proposed_price"] = result["price"]
        if result["email_sent"] or result["sms_sent"]:
            prospect["sent"] = True
            prospect["sentAt"] = datetime.now().isoformat()
            prospect["last_sent_price"] = result["price"]
        updated = True
    if updated:
        save_price_adaptator_data(data)

def price_adaptator_scheduler_loop():
    while True:
        try:
            process_price_adaptator_followups()
        except Exception as exc:
            logging.exception("[price-adaptator] Scheduler error: %s", exc)
        time.sleep(60 * 30)

def start_price_adaptator_scheduler():
    if os.environ.get("ENABLE_PRICE_ADAPTATOR_AUTOSEND", "").lower() != "true":
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    thread = threading.Thread(target=price_adaptator_scheduler_loop, daemon=True)
    thread.start()

def ensure_jury_defaults(session):
    session.setdefault("jurys", [])
    session.setdefault("jury_notification_status", "to_notify")
    for jury in session["jurys"]:
        jury.setdefault("id", str(uuid.uuid4())[:8])
        jury.setdefault("status", "pending")
        jury.setdefault("token", str(uuid.uuid4()))
        jury.setdefault("notified_at", None)
        jury.setdefault("reminded_at", None)

def ensure_global_jury_defaults(data):
    data.setdefault("jurys", [])
    for jury in data["jurys"]:
        jury.setdefault("id", str(uuid.uuid4())[:8])
        jury.setdefault("nom", "")
        jury.setdefault("prenom", "")
        jury.setdefault("email", "")
        jury.setdefault("telephone", "")

def find_global_jury_by_email(data, email):
    if not email:
        return None
    normalized = email.strip().lower()
    return next((j for j in data.get("jurys", []) if j.get("email", "").strip().lower() == normalized), None)

def find_global_jury_by_id(data, jury_id):
    return next((j for j in data.get("jurys", []) if j.get("id") == jury_id), None)

def sync_global_jurys(data):
    ensure_global_jury_defaults(data)
    for session in data.get("sessions", []):
        for jury in session.get("jurys", []):
            if not jury.get("email") and not jury.get("id"):
                continue
            existing = find_global_jury_by_email(data, jury.get("email"))
            if existing:
                existing.update({
                    "nom": jury.get("nom", existing.get("nom", "")),
                    "prenom": jury.get("prenom", existing.get("prenom", "")),
                    "email": jury.get("email", existing.get("email", "")),
                    "telephone": jury.get("telephone", existing.get("telephone", "")),
                })
                if not existing.get("id") and jury.get("id"):
                    existing["id"] = jury.get("id")
            elif find_global_jury_by_id(data, jury.get("id")) is None:
                data["jurys"].append({
                    "id": jury.get("id") or str(uuid.uuid4())[:8],
                    "nom": jury.get("nom", ""),
                    "prenom": jury.get("prenom", ""),
                    "email": jury.get("email", ""),
                    "telephone": jury.get("telephone", ""),
                })

def find_session(data, sid):
    for s in data["sessions"]:
        if s["id"] == sid:
            return s
    return None

def steps_rules_for_formation(formation):
    if formation in ("APS", "A3P", "DIRIGEANT"):
        rules = APS_A3P_STEPS
    elif formation == "SSIAP":
        rules = SSIAP_STEPS
    elif formation == "GENERAL":
        rules = GENERAL_STEPS
    else:
        return []

    return [rule for rule in rules if "formations" not in rule or formation in rule["formations"]]


def sync_steps(session):
    """Reconstruit les étapes selon le modèle officiel (ordre + ajout + évite doublons),
    tout en conservant done/done_at/custom_date des étapes existantes.
    """
    formation = session.get("formation")

    rules = steps_rules_for_formation(formation)
    if not rules:
        return

    # sécurité si steps absent
    session.setdefault("steps", [])

    # index existant par nom
    existing_by_name = {s.get("name"): s for s in session["steps"] if s.get("name")}

    new_steps = []
    for rule in rules:
        name = rule["name"]
        old = existing_by_name.get(name)

        # ✅ on conserve l'état existant si présent
        new_steps.append({
            "name": name,
            "done": bool(old.get("done")) if old else False,
            "done_at": old.get("done_at") if old else None,
            "custom_date": old.get("custom_date") if old else None
        })

    session["steps"] = new_steps


    # Récupère la liste actuelle des règles depuis le code
    rules = steps_rules_for_formation(formation)
    if not rules:
        return
    existing_names = [s["name"] for s in session.get("steps", [])]

    # Pour chaque étape officielle, si elle n’existe pas encore dans la session → on l’ajoute
    for rule in rules:
        if rule["name"] not in existing_names:
            session["steps"].append({
                "name": rule["name"],
                "done": False,
                "done_at": None
            })


# -----------------------
# Modèles d'étapes
# -----------------------
APS_A3P_STEPS = [
    {"name":"Création session CNAPS", "relative_to":"start", "offset_type":"before", "days":20},
    {"name":"Création session ADEF", "relative_to":"start", "offset_type":"before", "days":15},
    {"name":"Envoyer test de français", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Nomination jury examen", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Planification YPAREO", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Envoyer lien à compléter stagiaires", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Ajout des stagiaires sur DRACAR", "relative_to":"start", "offset_type":"before", "days":7},
    {"name":"Ajout des formateurs sur DRACAR", "relative_to":"start", "offset_type":"before", "days":7},
    {"name":"Contrat envoyé au formateur", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Contrat formateur imprimé", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Saisie des candidats ADEF", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Impression des fiches CNIL", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Fabrication badge formateur", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Vérification dossier formateur", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Corriger et imprimer test de français", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Validation session ADEF", "relative_to":"start", "offset_type":"before", "days":2},
    # AVANT EXAM
    {"name":"Saisie des SST", "relative_to":"exam", "offset_type":"before", "days":7},
    {"name":"Impression des SST", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Impression dossier fin de formation", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Impression évaluation de fin de formation", "relative_to":"exam", "offset_type":"before", "days":5},
    # JOUR EXAM
    {"name":"Session examen clôturée", "relative_to":"exam", "offset_type":"after", "days":0},
    {"name":"Frais ADEF réglés", "relative_to":"exam", "offset_type":"after", "days":0},
    {"name":"Documents examen envoyés à l’ADEF", "relative_to":"exam", "offset_type":"after", "days":0},
    # APRÈS EXAM
    {"name":"Envoyer mail stagiaires attestations de formation", "relative_to":"exam", "offset_type":"after", "days":2},
    {"name":"Message avis Google", "relative_to":"exam", "offset_type":"after", "days":2},
    {"name":"Diplômes reçus", "relative_to":"exam", "offset_type":"after", "days":7},
    {"name":"Diplômes envoyés aux stagiaires", "relative_to":"exam", "offset_type":"after", "days":10},
    {"name": "Saisie entrée en formation EDOF", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name":"Imprimer feuilles de présence et planning", "relative_to":"start", "offset_type":"before", "days":2},
    {"name":"Documents examens imprimés", "relative_to":"exam", "offset_type":"before", "days":1},
    {"name": "Signature fiches CNIL", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name":"Fin de formation EDOF", "relative_to":"exam", "offset_type":"after", "days":1},
    {"name": "Signature registre entretien SST", "relative_to": "start", "offset_type": "after", "days": 15},
    {"name": "Distribution des t-shirts", "relative_to": "start", "offset_type": "after", "days": 1, "formations": ["A3P"]},
    {"name": "Récupérer paiement logement", "relative_to": "start", "offset_type": "after", "days": 0, "formations": ["A3P"]},
    {"name":"Préparation planning de ménage", "relative_to":"start", "offset_type":"before", "days":2, "formations": ["A3P"]},
    {"name":"Créer groupe Whatsapp", "relative_to":"start", "offset_type":"before", "days":7},
]

SSIAP_STEPS = [

    # ============================
    # 📌 SESSION — Article 4
    # ============================
    {"name": "Le formateur a été nommé (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "Le contrat d'intervention a été envoyé au formateur (7 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 7},
    {"name": "Le contrat d'intervention formateur a été signé et imprimé (5 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 5},
    {"name": "Le nombre de candidats est de 12 maximum (2 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 2},
    {"name": "La préfecture a été avisée de l'ouverture de la session 2 mois avant le démarrage (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "La préfecture a été avisée de la date d'examen 2 mois avant le démarrage (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "Les convocations en formation ont été envoyées aux candidats (15 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 15},
    {"name": "Le test de français a été envoyé à tous les candidats (7 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 7},

    # =======================================
    # 📌 DOSSIER CANDIDAT (formation)
    # =======================================
    {"name": "Le dossier comporte la pièce d'identité de chaque candidat (1er jour de formation)", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name": "Le dossier comporte l'attestation de formation au secourisme de chaque candidat (1er jour de formation)", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name": "Le dossier comporte 2 photos d'identité (1 archive, 1 diplôme) pour chaque candidat (1er jour de formation)", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name": "Le dossier comporte le certificat médical conforme à l'Annexe VII de l'arrêté du 2 mai 2005 modifié de chaque candidat (1er jour de formation)", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name": "Le dossier comporte une copie du test de français réalisé par chaque candidat en amont de la formation (1er jour de formation)", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name": "Le dossier comporte le contrat de formation signé par chaque candidat (1er jour de formation)", "relative_to": "start", "offset_type": "after", "days": 0},
    {"name": "Les dossiers de chaque candidat ont été vérifiés avant le démarrage de la session (1er jour de formation)", "relative_to": "start", "offset_type": "after", "days": 0},

    # =======================================
    # 📌 DEMANDE PRÉSIDENCE JURY SDIS (Art 8)
    # =======================================
    {"name": "Le SDIS a été avisé de la date d'organisation des épreuves (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "La demande comporte le nom, la fonction et la qualification du jury chef de service incendie (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "La demande comporte l'attestation d'engagement (accord) du jury chef de service incendie (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "L'engagement écrit, du propriétaire ou de l'exploitant de l'établissement, de mettre à disposition les locaux et d'autoriser la manipulation des installations techniques nécessaires au déroulement de l'épreuve pratique est fournit (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "Le planning de la session est fournit (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "Sur le planning le nom, la qualité, la fonction et les qualifications des formateurs sont indiqués (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "La convention de demande de présidence jury SDIS en fournit en double exemplaire (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "La demande de présidence de jury SDIS a été envoyé en LRAR (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},

    # =======================================
    # 📌 DOSSIER CANDIDAT (examen)
    # =======================================
    {"name": "Les dossiers examen des candidats sont imprimés pour les membres du jury (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte la pièce d'identité du candidat (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte l'attestation de formation au secourisme (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte le certificat médical conforme à l'Annexe VII de l'arrêté du 2 mai 2005 modifié (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte le test de français réalisé par le candidat en amont de la formation (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte le certificat de réalisation de la formation (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte le PV d'examen individuel pré-rempli (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte une attestation du directeur certifiant que les candidats ne travaillent pas dans la même entreprise que le jury (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Chaque dossier examen comporte une attestation du directeur certifiant que les candidats sont capables d'écrire une main courante (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},

    # =======================================
    # 📌 ORGANISATION DE L’EXAMEN
    # =======================================
    {"name": "Le jury chef de service de sécurité incendie a été nommé (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "Le lieu d'examen (pratique) a été réservé (65 jours avant début de session)", "relative_to": "start", "offset_type": "before", "days": 65},
    {"name": "Les convocations à l'examen ont été envoyées aux candidats (15 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 15},
    {"name": "Les télécommandes QUIZZBOX ont été vérifiées en vue de l'examen (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Le logiciel QUIZZBOX a été paramétré pour l'examen (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Le procès verbal collectif a été pré-rempli et imprimé (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "La salle d'examen théorique a été préparée et vérifiée (2 jours avant l'examen)", "relative_to": "exam", "offset_type": "before", "days": 2},
    {"name": "Les pièces d'identité des candidats ont été vérifié par le jury (jour de l'examen)", "relative_to": "exam", "offset_type": "after", "days": 0},
    {"name": "Le PV de résultats examen théorique (QCM Quizzbox) a été imprimé en double exemplaire : SDIS et archives (jour de l'examen)", "relative_to": "exam", "offset_type": "after", "days": 0},
    {"name": "A l'issue de l'examen les PV d'examen individuels ont été photocopiés en triples exemplaires : SDIS, candidats et archives (jour de l'examen)", "relative_to": "exam", "offset_type": "after", "days": 0},
    {"name": "A l'issue de l'examen le PV d'examen collectif a été photocopié en doubles exemplaires : SDIS et archives (jour de l'examen)", "relative_to": "exam", "offset_type": "after", "days": 0},

    # =======================================
    # 📌 DIPLÔMES — Annexe VIII / Article 11
    # =======================================
    {"name": "Chaque diplôme comporte une photographie couleur dans l'angle droit (2 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "Les numéros de diplômes ont été vérifiés (2 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "La signature du directeur du centre de formation agréé est apposée dans l'angle inférieur gauche (2 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "Les diplômes ont été imprimé sur du papier rigide 180g (2 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "Les diplômes ont été envoyés au SDIS en LRAR (2 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "Les diplômes ont été validé par le SDIS (30 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 30},
    {"name": "Les diplômes ont été distribués aux candidats (35 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 35},
    {"name": "Les candidats ont signé le récépissé de délivrance, preuve de remise du diplôme (35 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 35},
    {"name": "Les diplômes sont référencés dans un tableau Excel pour assurer la traçabilité (2 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 2},

    # =======================================
    # 📌 CLÔTURE DE SESSION
    # =======================================
    {"name": "Le rapport de traçabilité et de conformité a été généré (40 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 40},
    {"name": "Le rapport de traçabilité et de conformité a été envoyé par mail à la préfecture (40 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 40},
    {"name": "Le rapport de traçabilité et de conformité a été imprimé et archivé (40 jours après l'examen)", "relative_to": "exam", "offset_type": "after", "days": 40},
]


GENERAL_STEPS = [
    {"name": "Vérification des extincteurs", "fixed_date": "2026-10-15"},
    {"name": "Contrôle des installations électriques", "fixed_date": "2026-09-10"},
    {"name": "Vérification SSI", "fixed_date": "2026-08-15"},
    {"name": "Contrôle climatisation", "fixed_date": "2026-09-10"},
    {"name": "Inscriptions examen BTS", "fixed_date": "2026-09-10"},
    {"name": "Renouvellement agrément CNAPS", "fixed_date": "2026-09-01"},
]


FORMATION_COLORS = {
    "APS": "#1b9aaa",
    "A3P": "#2a9134",
    "SSIAP": "#c0392b",
    "DIRIGEANT": "#8e44ad",
    "GENERAL": "#d4ac0d",
}

FORMATION_LABELS = {
    "APS": "Agent de Prévention et de Sécurité",
    "A3P": "Agent de Protection Rapprochée (A3P)",
    "SSIAP": "Service de Sécurité Incendie et d’Assistance à Personnes (SSIAP)",
    "DIRIGEANT": "Dirigeant",
    "GENERAL": "Général",
}

def formation_label(value):
    return FORMATION_LABELS.get(value, value)
app.jinja_env.filters['formation_label'] = formation_label

def default_steps_for(formation):
    steps = steps_rules_for_formation(formation)
    return [{"name": s["name"], "done": False, "done_at": None} for s in steps]


# -----------------------
# Statuts / échéances
# -----------------------
def _rule_for(formation, step_index):
    rules = steps_rules_for_formation(formation)

    # ✅ Protection anti IndexError
    if step_index < 0 or step_index >= len(rules):
        return None

    return rules[step_index]



def parse_date(date_str):
    """Accepte les formats AAAA-MM-JJ ou JJ/MM/AAAA"""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def deadline_for(step_index, session):
    rule = _rule_for(session["formation"], step_index)

    # ✅ Si cette étape a une date personnalisée enregistrée dans la session → priorité
    custom_date = session["steps"][step_index].get("custom_date")
    if custom_date:
        return parse_date(custom_date)

    if not rule:
        return None

    # ✅ Si l’étape a une date fixe → on la renvoie directement
    if "fixed_date" in rule and rule["fixed_date"]:
        return parse_date(rule["fixed_date"])

    # Sinon on garde le comportement classique (start/exam + offset)
    base_date = parse_date(session.get("date_exam")) if rule["relative_to"] == "exam" else parse_date(session.get("date_debut"))
    if not base_date:
        return None
    return (base_date - timedelta(days=rule["days"])) if rule["offset_type"] == "before" else (base_date + timedelta(days=rule["days"]))



def status_for_step(step_index, session, now=None):
    if now is None:
        now = datetime.now()
    dl = deadline_for(step_index, session)
    if dl is None:
        return ("n/a", None)
    step = session["steps"][step_index]
    if step["done"]:
        return ("done", dl)

    # --- 🔧 Correction : tolérance réelle sur les 24 h ---
    diff_days = (dl.date() - now.date()).days
    if diff_days < 0:
        return ("late", dl)
    elif diff_days == 0:
        return ("on_time", dl)
    elif diff_days == 1:
        return ("upcoming", dl)  # échéance demain → "à venir"
    else:
        return ("on_time", dl)



# ✅ Fonction spéciale pour le template Jinja
def status_for_step_jinja(i, s):
    return status_for_step(i, s, now=datetime.now())

def snapshot_overdue(session):
    overdue = []
    for i, step in enumerate(session["steps"]):
        st, dl = status_for_step(i, session)
        if st == "late":
            overdue.append((step["name"], dl))
    overdue.sort(key=lambda x: (x[1] or datetime.max))
    return overdue

# -----------------------
# Archivage automatique
# -----------------------
def auto_archive_if_all_done(session):
    session["archived"] = all(step["done"] for step in session["steps"])

# -----------------------
# Mails & résumé
# -----------------------
def _late_phrase(dl: datetime) -> str:
    if not dl:
        return "Retard (date N/A)"
    days = (datetime.now().date() - dl.date()).days
    days = max(days, 0)
    return f"Retard de {days} jour{'s' if days>1 else ''} ({dl.strftime('%d-%m-%Y')})"

def normalize_phone_number(value: str):
    if not value:
        return None
    cleaned = value.replace(" ", "").replace(".", "").replace("-", "").replace("(", "").replace(")", "")
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    elif cleaned.startswith("0"):
        cleaned = "+33" + cleaned[1:]
    if not cleaned.startswith("+"):
        return None
    return cleaned

def generate_daily_overdue_email(sessions):
    now_txt = datetime.now().strftime("%d-%m-%Y %H:%M")
    logo_path = os.path.join("static", "img", "logo-integrale.png")
    logo_base64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode("utf-8")

    html = f"""
    <body style="font-family:Arial,Helvetica,sans-serif;background:#f7f7f7;margin:0;padding:0;">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f7f7f7;">
        <tr>
          <td align="center" style="padding:20px 10px;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width:600px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.1);">
              <tr>
                <td style="background:#121212;color:#fff;padding:20px;text-align:center;">
                  {('<img src="data:image/png;base64,'+logo_base64+'" alt="Intégrale Academy" style="width:100%;max-width:250px;height:auto;margin-bottom:10px;border-radius:12px;">') if logo_base64 else ''}
                  <h1 style="margin:10px 0;font-size:20px;">⚠️ Récapitulatif des retards — Intégrale Academy</h1>
                  <div style="font-size:13px;opacity:.9;">{now_txt}</div>
                </td>
              </tr>

              <tr>
                <td style="padding:20px 18px;">
    """

    found_any = False
    for s in sessions:
        # On ignore les sessions archivées dans le mail quotidien
        # pour éviter d'afficher d'anciennes formations en doublon.
        if s.get("archived"):
            continue
        overdue = snapshot_overdue(s)
        if not overdue:
            continue
        found_any = True
        color = FORMATION_COLORS.get(s["formation"], "#999")
        html += f"""
          <div style="border:1px solid #eee;border-radius:12px;padding:18px 20px;margin-bottom:18px;">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;">
              <div style="background:{color};color:#fff;font-weight:700;border-radius:30px;padding:6px 14px;font-size:14px;letter-spacing:.5px;">{s["formation"]}</div>
              <div style="font-size:14px;color:#444;margin-top:8px;">
                <b>Début :</b> {format_date(s.get("date_debut","—"))} &nbsp;&nbsp;
                <b>Fin :</b> {format_date(s.get("date_fin","—"))} &nbsp;&nbsp;
                <b>Examen :</b> {format_date(s.get("date_exam","—"))}
              </div>
            </div>
            <ul style="margin:12px 0 0 18px;padding:0;color:#333;font-size:15px;line-height:1.6;">
        """
        for name, dl in overdue:
            html += f"<li style='margin-bottom:4px;list-style:none;'>🔸 {name} — {_late_phrase(dl)}</li>"
        html += "</ul></div>"

    if not found_any:
        html += "<p style='text-align:center;font-size:15px;color:#444;margin:20px 0;'>✅ Aucun retard à signaler aujourd’hui.</p>"

    html += """
                </td>
              </tr>
              <tr>
                <td style="background:#fafafa;text-align:center;padding:14px;font-size:13px;color:#666;">
                  Vous recevez ce mail automatiquement chaque matin à 8h.
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    """
    return html

def get_smtp_config():
    if BREVO_SMTP_KEY:
        brevo_login = BREVO_SMTP_LOGIN or "apikey"
        return {
            "server": BREVO_SMTP_SERVER,
            "port": BREVO_SMTP_PORT,
            "login": brevo_login,
            "password": BREVO_SMTP_KEY,
            "from_email": BREVO_FROM_EMAIL or FROM_EMAIL or BREVO_SMTP_LOGIN,
        }
    return {
        "server": SMTP_SERVER,
        "port": SMTP_PORT,
        "login": FROM_EMAIL,
        "password": EMAIL_PASSWORD,
        "from_email": FROM_EMAIL,
    }

def send_daily_overdue_summary():
    smtp_config = get_smtp_config()
    if not smtp_config["login"] or not smtp_config["password"]:
        print("⚠️ EMAIL non configuré")
        return
    data = load_sessions()
    sessions = data["sessions"]
    html = generate_daily_overdue_email(sessions)
    msg = MIMEText(html, "html", _charset="utf-8")
    msg["Subject"] = "⚠️ Récapitulatif des retards — Intégrale Academy"
    msg["From"] = smtp_config["from_email"]
    msg["To"] = "clement@integraleacademy.com"
    try:
        with smtplib.SMTP(smtp_config["server"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["login"], smtp_config["password"])
            server.sendmail(smtp_config["from_email"], ["clement@integraleacademy.com"], msg.as_string())
        print("✅ Mail quotidien envoyé avec succès")
    except Exception as e:
        print("❌ Erreur envoi mail quotidien :", e)


def _list_formateur_expired_documents(formateurs):
    today = datetime.now().date()
    expired_docs = []

    for formateur in formateurs:
        nom = (formateur.get("nom") or "").upper().strip()
        prenom = (formateur.get("prenom") or "").strip()
        full_name = f"{prenom} {nom}".strip()

        for doc in formateur.get("documents", []):
            exp_str = (doc.get("expiration") or "").strip()
            if not exp_str:
                continue

            exp_dt = parse_date(exp_str)
            if not exp_dt or exp_dt.date() > today:
                continue

            # Une seule alerte par document et par date d'expiration
            if doc.get("expiration_alert_sent_for") == exp_str:
                continue

            expired_docs.append({
                "formateur_id": formateur.get("id"),
                "formateur_nom": full_name,
                "label": doc.get("label", "Document"),
                "expiration": exp_str,
                "doc": doc,
            })

    return expired_docs


def send_formateur_expiration_alerts():
    smtp_config = get_smtp_config()
    if not smtp_config["login"] or not smtp_config["password"]:
        print("⚠️ SMTP non configuré pour les alertes formateurs")
        return 0

    formateurs = load_formateurs()
    expired_docs = _list_formateur_expired_documents(formateurs)
    if not expired_docs:
        return 0

    html_items = ""
    for item in expired_docs:
        html_items += (
            f"<li><b>{item['formateur_nom'] or 'Formateur sans nom'}</b> — "
            f"{item['label']} (expiration : {format_date(item['expiration'])})</li>"
        )

    now_txt = datetime.now().strftime("%d-%m-%Y %H:%M")
    html = f"""
    <div style=\"font-family:Arial,Helvetica,sans-serif;color:#222;line-height:1.5;\">
      <h2 style=\"margin-bottom:8px;\">⚠️ Documents formateurs expirés</h2>
      <p style=\"margin-top:0;\">Détection automatique du {now_txt}.</p>
      <p>Les documents suivants sont arrivés à expiration :</p>
      <ul>{html_items}</ul>
    </div>
    """

    msg = MIMEText(html, "html", _charset="utf-8")
    msg["Subject"] = "⚠️ Alerte expiration documents formateurs"
    msg["From"] = smtp_config["from_email"]
    msg["To"] = "clement@integraleacademy.com"

    try:
        with smtplib.SMTP(smtp_config["server"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["login"], smtp_config["password"])
            server.sendmail(
                smtp_config["from_email"],
                ["clement@integraleacademy.com"],
                msg.as_string(),
            )

        for item in expired_docs:
            item["doc"]["expiration_alert_sent_for"] = item["expiration"]
            item["doc"]["expiration_alert_sent_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_formateurs(formateurs)

        print(f"✅ Alertes expiration formateurs envoyées ({len(expired_docs)} document(s))")
        return len(expired_docs)
    except Exception as e:
        print("❌ Erreur envoi alertes expiration formateurs :", e)
        return 0


def build_jury_invitation_html(session, jury, yes_url, no_url):
    formation = formation_label(session.get("formation", "—"))
    date_exam = format_date(session.get("date_exam", "—"))
    full_name = f"{jury.get('prenom','').strip()} {jury.get('nom','').strip()}".strip()
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;color:#222;line-height:1.6;">
      <p>Bonjour{',' if full_name else ''} {full_name}</p>
      <p>
        Nous vous proposons d'intervenir en tant que membre de jury de notre session
        <strong>{formation}</strong>, le <strong>{date_exam}</strong>.
      </p>
      <p>Pourriez-vous svp me confirmer votre présence pour cet examen ?</p>
      <div style="margin:20px 0;">
        <a href="{yes_url}" style="display:inline-block;background:#2a9134;color:#fff;text-decoration:none;padding:10px 16px;border-radius:6px;font-weight:600;margin-right:10px;">
          JE CONFIRME MA PRESENCE
        </a>
        <a href="{no_url}" style="display:inline-block;background:#c0392b;color:#fff;text-decoration:none;padding:10px 16px;border-radius:6px;font-weight:600;">
          JE NE SERAI PAS DISPONIBLE A CETTE DATE
        </a>
      </div>
      <p>Merci par avance,</p>
      <p style="margin-top:10px;">
        Clément VAILLANT<br>
        Intégrale Academy
      </p>
    </div>
    """


def send_jury_invitation_email(session, jury, yes_url, no_url):
    to_email = jury.get("email", "").strip()
    if not to_email:
        print("[jury email] Email jury manquant")
        return False, "Email jury manquant"
    html = build_jury_invitation_html(session, jury, yes_url, no_url)
    if BREVO_API_KEY and (BREVO_SENDER_EMAIL or BREVO_FROM_EMAIL or FROM_EMAIL):
        print("[jury email] Envoi via Brevo API")
        sender_email = BREVO_SENDER_EMAIL or BREVO_FROM_EMAIL or FROM_EMAIL
        sender_name = BREVO_SENDER_NAME or "Intégrale Academy"
        payload = json.dumps({
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": to_email}],
            "subject": f"Invitation jury — Session {session.get('formation', 'Formation')}",
            "htmlContent": html,
        }).encode("utf-8")
        request_obj = urllib.request.Request("https://api.brevo.com/v3/smtp/email")
        request_obj.add_header("Content-Type", "application/json")
        request_obj.add_header("api-key", BREVO_API_KEY)
        try:
            with urllib.request.urlopen(request_obj, data=payload, timeout=10) as response:
                if 200 <= response.status < 300:
                    print("[jury email] Brevo API OK", response.status)
                    return True, "Email envoyé"
                body = response.read().decode("utf-8")
                print("[jury email] Brevo API erreur", response.status, body)
                return False, f"Erreur email: {response.status} {body}"
        except Exception as e:
            print("[jury email] Brevo API exception", e)
            return False, f"Erreur email: {e}"
    if BREVO_API_KEY and not (BREVO_SENDER_EMAIL or BREVO_FROM_EMAIL or FROM_EMAIL):
        print("[jury email] Brevo API configurée mais expéditeur manquant")

    smtp_config = get_smtp_config()
    if not smtp_config["login"] or not smtp_config["password"]:
        print("[jury email] SMTP non configuré", {
            "server": smtp_config["server"],
            "login_set": bool(smtp_config["login"]),
            "password_set": bool(smtp_config["password"]),
            "from_set": bool(smtp_config["from_email"]),
        })
        return False, "EMAIL non configuré"
    msg = MIMEText(html, "html", _charset="utf-8")
    msg["Subject"] = f"Invitation jury — Session {session.get('formation', 'Formation')}"
    msg["From"] = smtp_config["from_email"]
    msg["To"] = to_email
    try:
        print("[jury email] Envoi via SMTP", {
            "server": smtp_config["server"],
            "port": smtp_config["port"],
            "from": smtp_config["from_email"],
            "to": to_email,
        })
        with smtplib.SMTP(smtp_config["server"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["login"], smtp_config["password"])
            server.sendmail(smtp_config["from_email"], [to_email], msg.as_string())
        print("[jury email] SMTP OK")
        return True, "Email envoyé"
    except Exception as e:
        print("[jury email] SMTP exception", e)
        return False, f"Erreur email: {e}"


def send_jury_sms(session, jury, yes_url, no_url):
    to_number = jury.get("telephone", "").strip()
    if not to_number:
        print("[jury sms] Téléphone jury manquant")
        return False, "Téléphone jury manquant"
    normalized_number = normalize_phone_number(to_number)
    if not normalized_number:
        print("[jury sms] Téléphone jury invalide", to_number)
        return False, "Téléphone jury au format international requis (ex: +336...)"
    formation = formation_label(session.get("formation", "—"))
    date_exam = format_date(session.get("date_exam", "—"))
    message = (
        "Bonjour,\n\n"
        f"Nous vous proposons d'intervenir en tant que membre de jury de notre session {formation}, le {date_exam}.\n\n"
        "Pourriez-vous svp me confirmer votre présence pour cet examen ?\n"
        f"JE CONFIRME MA PRESENCE: {yes_url}\n"
        f"JE NE SERAI PAS DISPONIBLE A CETTE DATE: {no_url}\n\n"
        "Merci par avance,\n"
        "Clément VAILLANT\n"
        "Intégrale Academy"
    )

    if BREVO_API_KEY and BREVO_SMS_SENDER:
        print("[jury sms] Envoi via Brevo API")
        payload = json.dumps({
            "sender": BREVO_SMS_SENDER,
            "recipient": normalized_number,
            "content": message,
            "type": "transactional",
        }).encode("utf-8")
        request_obj = urllib.request.Request("https://api.brevo.com/v3/transactionalSMS/sms")
        request_obj.add_header("Content-Type", "application/json")
        request_obj.add_header("api-key", BREVO_API_KEY)
        try:
            with urllib.request.urlopen(request_obj, data=payload, timeout=10) as response:
                if 200 <= response.status < 300:
                    print("[jury sms] Brevo API OK", response.status)
                    return True, "SMS envoyé"
                body = response.read().decode("utf-8")
                print("[jury sms] Brevo API erreur", response.status, body)
                return False, f"Erreur SMS: {response.status} {body}"
        except Exception as e:
            print("[jury sms] Brevo API exception", e)
            return False, f"Erreur SMS: {e}"
    elif BREVO_API_KEY and not BREVO_SMS_SENDER:
        print("[jury sms] Brevo API configurée mais sender manquant")
        return False, "SMS non configuré: BREVO_SMS_SENDER manquant"

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    if not account_sid or not auth_token or not from_number:
        print("[jury sms] Twilio non configuré", {
            "account_sid_set": bool(account_sid),
            "auth_token_set": bool(auth_token),
            "from_number_set": bool(from_number),
        })
        return False, "SMS non configuré"
    payload = urllib.parse.urlencode({
        "From": from_number,
        "To": normalized_number,
        "Body": message
    }).encode("utf-8")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    request_obj = urllib.request.Request(url, data=payload, method="POST")
    auth_header = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("utf-8")
    request_obj.add_header("Authorization", f"Basic {auth_header}")
    try:
        print("[jury sms] Envoi via Twilio", {"from": from_number, "to": normalized_number})
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            if 200 <= response.status < 300:
                print("[jury sms] Twilio OK", response.status)
                return True, "SMS envoyé"
            print("[jury sms] Twilio erreur", response.status)
            return False, f"Erreur SMS: {response.status}"
    except Exception as e:
        print("[jury sms] Twilio exception", e)
        return False, f"Erreur SMS: {e}"

def build_jury_reminder_html(session, jury, yes_url, no_url):
    formation = formation_label(session.get("formation", "Formation"))
    date_exam = format_date(session.get("date_exam", ""))
    full_name = f"{jury.get('prenom','').strip()} {jury.get('nom','').strip()}".strip()
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;line-height:1.6;color:#222;">
      <h2>Rappel : jury d'examen</h2>
      <p>Bonjour {full_name or "membre du jury"},</p>
      <p>
        Petit rappel concernant votre participation au jury de la session
        <strong>{formation}</strong> prévue le <strong>{date_exam}</strong>.
      </p>
      <p>Merci de confirmer votre présence :</p>
      <p>
        <a href="{yes_url}" style="background:#2a9134;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;margin-right:8px;">✅ Présent</a>
        <a href="{no_url}" style="background:#c0392b;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;">❌ Absent</a>
      </p>
      <p>Merci pour votre retour.</p>
    </div>
    """

def send_jury_reminder_email(session, jury, yes_url, no_url):
    to_email = jury.get("email", "").strip()
    if not to_email:
        print("[jury reminder email] Email jury manquant")
        return False, "Email jury manquant"
    html = build_jury_reminder_html(session, jury, yes_url, no_url)
    if BREVO_API_KEY and (BREVO_SENDER_EMAIL or BREVO_FROM_EMAIL or FROM_EMAIL):
        print("[jury reminder email] Envoi via Brevo API")
        sender_email = BREVO_SENDER_EMAIL or BREVO_FROM_EMAIL or FROM_EMAIL
        sender_name = BREVO_SENDER_NAME or "Intégrale Academy"
        payload = json.dumps({
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": to_email}],
            "subject": f"Rappel jury — Session {session.get('formation', 'Formation')}",
            "htmlContent": html,
        }).encode("utf-8")
        request_obj = urllib.request.Request("https://api.brevo.com/v3/smtp/email")
        request_obj.add_header("Content-Type", "application/json")
        request_obj.add_header("api-key", BREVO_API_KEY)
        try:
            with urllib.request.urlopen(request_obj, data=payload, timeout=10) as response:
                if 200 <= response.status < 300:
                    print("[jury reminder email] Brevo API OK", response.status)
                    return True, "Email rappel envoyé"
                body = response.read().decode("utf-8")
                print("[jury reminder email] Brevo API erreur", response.status, body)
                return False, f"Erreur email: {response.status} {body}"
        except Exception as e:
            print("[jury reminder email] Brevo API exception", e)
            return False, f"Erreur email: {e}"
    if BREVO_API_KEY and not (BREVO_SENDER_EMAIL or BREVO_FROM_EMAIL or FROM_EMAIL):
        print("[jury reminder email] Brevo API configurée mais expéditeur manquant")

    smtp_config = get_smtp_config()
    if not smtp_config["login"] or not smtp_config["password"]:
        print("[jury reminder email] SMTP non configuré", {
            "server": smtp_config["server"],
            "login_set": bool(smtp_config["login"]),
            "password_set": bool(smtp_config["password"]),
            "from_set": bool(smtp_config["from_email"]),
        })
        return False, "EMAIL non configuré"
    msg = MIMEText(html, "html", _charset="utf-8")
    msg["Subject"] = f"Rappel jury — Session {session.get('formation', 'Formation')}"
    msg["From"] = smtp_config["from_email"]
    msg["To"] = to_email
    try:
        print("[jury reminder email] Envoi via SMTP", {
            "server": smtp_config["server"],
            "port": smtp_config["port"],
            "from": smtp_config["from_email"],
            "to": to_email,
        })
        with smtplib.SMTP(smtp_config["server"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["login"], smtp_config["password"])
            server.sendmail(smtp_config["from_email"], [to_email], msg.as_string())
        print("[jury reminder email] SMTP OK")
        return True, "Email rappel envoyé"
    except Exception as e:
        print("[jury reminder email] SMTP exception", e)
        return False, f"Erreur email: {e}"

def send_jury_reminder_sms(session, jury, yes_url, no_url):
    to_number = jury.get("telephone", "").strip()
    if not to_number:
        print("[jury reminder sms] Téléphone jury manquant")
        return False, "Téléphone jury manquant"
    normalized_number = normalize_phone_number(to_number)
    if not normalized_number:
        print("[jury reminder sms] Téléphone jury invalide", to_number)
        return False, "Téléphone jury au format international requis (ex: +336...)"
    formation = formation_label(session.get("formation", "—"))
    date_exam = format_date(session.get("date_exam", "—"))
    message = (
        f"Rappel jury {formation} du {date_exam}. "
        f"Présent: {yes_url} / Absent: {no_url}"
    )

    if BREVO_API_KEY and BREVO_SMS_SENDER:
        print("[jury reminder sms] Envoi via Brevo API")
        payload = json.dumps({
            "sender": BREVO_SMS_SENDER,
            "recipient": normalized_number,
            "content": message,
            "type": "transactional",
        }).encode("utf-8")
        request_obj = urllib.request.Request("https://api.brevo.com/v3/transactionalSMS/sms")
        request_obj.add_header("Content-Type", "application/json")
        request_obj.add_header("api-key", BREVO_API_KEY)
        try:
            with urllib.request.urlopen(request_obj, data=payload, timeout=10) as response:
                if 200 <= response.status < 300:
                    print("[jury reminder sms] Brevo API OK", response.status)
                    return True, "SMS rappel envoyé"
                body = response.read().decode("utf-8")
                print("[jury reminder sms] Brevo API erreur", response.status, body)
                return False, f"Erreur SMS: {response.status} {body}"
        except Exception as e:
            print("[jury reminder sms] Brevo API exception", e)
            return False, f"Erreur SMS: {e}"
    elif BREVO_API_KEY and not BREVO_SMS_SENDER:
        print("[jury reminder sms] Brevo API configurée mais sender manquant")
        return False, "SMS non configuré: BREVO_SMS_SENDER manquant"

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    if not account_sid or not auth_token or not from_number:
        print("[jury reminder sms] Twilio non configuré", {
            "account_sid_set": bool(account_sid),
            "auth_token_set": bool(auth_token),
            "from_number_set": bool(from_number),
        })
        return False, "SMS non configuré"
    payload = urllib.parse.urlencode({
        "From": from_number,
        "To": normalized_number,
        "Body": message
    }).encode("utf-8")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    request_obj = urllib.request.Request(url, data=payload, method="POST")
    auth_header = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("utf-8")
    request_obj.add_header("Authorization", f"Basic {auth_header}")
    try:
        print("[jury reminder sms] Envoi via Twilio", {"from": from_number, "to": normalized_number})
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            if 200 <= response.status < 300:
                print("[jury reminder sms] Twilio OK", response.status)
                return True, "SMS rappel envoyé"
            print("[jury reminder sms] Twilio erreur", response.status)
            return False, f"Erreur SMS: {response.status}"
    except Exception as e:
        print("[jury reminder sms] Twilio exception", e)
        return False, f"Erreur SMS: {e}"

def send_jury_reminders(data, base_url):
    today = datetime.now().date()
    reminded = []
    for session in data.get("sessions", []):
        if session.get("archived"):
            continue
        ensure_jury_defaults(session)
        date_exam = parse_date(session.get("date_exam"))
        if not date_exam:
            continue
        if (date_exam.date() - today).days != 5:
            continue
        for jury in session.get("jurys", []):
            if jury.get("status") in ("present", "absent"):
                continue
            if jury.get("reminded_at"):
                continue
            token = jury.get("token") or str(uuid.uuid4())
            jury["token"] = token
            yes_url = f"{base_url}{url_for('jury_response', sid=session['id'], jid=jury['id'], response='present')}?token={token}"
            no_url = f"{base_url}{url_for('jury_response', sid=session['id'], jid=jury['id'], response='absent')}?token={token}"
            email_ok, _ = send_jury_reminder_email(session, jury, yes_url, no_url)
            sms_ok, _ = send_jury_reminder_sms(session, jury, yes_url, no_url)
            if email_ok or sms_ok:
                jury["reminded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                reminded.append(f"{jury.get('prenom','')} {jury.get('nom','')}")
    return reminded

# ------------------------------------------------------------
# 🔐 Authentification simple pour la préfecture (HTTP Basic)
# ------------------------------------------------------------
from functools import wraps
from flask import request, Response

def pref_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == "prefecture" and auth.password == "pref2025"):
            return Response(
                "Accès réservé à la préfecture.\n",
                401,
                {"WWW-Authenticate": 'Basic realm="Accès Préfecture"'}
            )
        return f(*args, **kwargs)
    return decorated

# ------------------------------------------------------------
# 📋 Résumé conformité globale formateurs (pour l'index)
# ------------------------------------------------------------
def get_formateurs_global_non_conformites():
    formateurs = load_formateurs()
    total_non_conformes = 0

    for f in formateurs:
        for doc in f.get("documents", []):
            auto_update_document_status(doc)
            if doc.get("status") in ("non_conforme", "a_controler"):
                total_non_conformes += 1


    return total_non_conformes




# -----------------------
# Routes principales
# -----------------------
@app.route("/")
def index():
    nb_non_conformes = get_formateurs_global_non_conformites()

    return render_template(
        "index.html",
        title="Plateforme de gestion Intégrale Academy",
        formateurs_non_conformes=nb_non_conformes,
        shortcuts=load_shortcuts()
    )


@app.route("/shortcuts", methods=["GET"])
def shortcuts_data():
    return jsonify(load_shortcuts())


@app.route("/shortcuts", methods=["POST"])
def create_shortcut():
    name = (request.form.get("name") or "").strip()
    url = (request.form.get("url") or "").strip()
    image = request.files.get("image")

    if not name or not url:
        return jsonify({"ok": False, "error": "Le nom et le lien sont obligatoires."}), 400

    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "Le lien doit commencer par http:// ou https://"}), 400

    if image is None or not image.filename:
        return jsonify({"ok": False, "error": "Veuillez importer une image."}), 400

    if not allowed_shortcut_image(image.filename):
        return jsonify({"ok": False, "error": "Format d'image non pris en charge."}), 400

    ensure_shortcuts_storage()
    original_name = secure_filename(image.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    image.save(os.path.join(SHORTCUT_UPLOAD_DIR, filename))

    shortcuts = load_shortcuts()
    shortcut = {
        "id": uuid.uuid4().hex,
        "name": name,
        "url": url,
        "image": url_for("static", filename=f"uploads/shortcuts/{filename}")
    }
    shortcuts.append(shortcut)
    save_shortcuts(shortcuts)
    return jsonify({"ok": True, "shortcut": shortcut}), 201


@app.route("/general-tools")
def general_tools():
    return render_template("general_tools.html", title="Outils généraux")


@app.route("/price-adaptator")
def price_adaptator():
    return render_template("price_adaptator.html", title="Price adaptator")


@app.route("/price-adaptator/data")
def price_adaptator_data():
    data = load_price_adaptator_data()
    return {"prospects": data.get("prospects", []), "dates": data.get("dates", {})}


@app.route("/price-adaptator/prospects", methods=["POST"])
def price_adaptator_add_prospect():
    payload = request.get_json(silent=True) or {}
    nom = normalize_price_adaptator_nom(payload.get("nom"))
    prenom = normalize_price_adaptator_prenom(payload.get("prenom"))
    cpf = payload.get("cpf")
    email = (payload.get("email", "") or "").strip()
    telephone = (payload.get("telephone", "") or "").strip()
    formation = (payload.get("formation", "") or "").strip()

    if not (nom and prenom and formation):
        return {"ok": False, "error": "Données prospect incomplètes"}, 400

    try:
        cpf_value = float(cpf)
        if cpf_value < 0:
            raise ValueError
    except (TypeError, ValueError):
        return {"ok": False, "error": "Montant CPF invalide"}, 400

    data = load_price_adaptator_data()
    prospect = {
        "id": str(uuid.uuid4()),
        "nom": nom,
        "prenom": prenom,
        "cpf": cpf_value,
        "email": email,
        "telephone": telephone,
        "formation": formation,
        "sent": False,
        "sentAt": None,
        "proposed_price": None,
        "last_error": None,
        "last_attempt_at": None,
        "created_at": datetime.now().isoformat(),
    }
    data["prospects"].insert(0, prospect)
    save_price_adaptator_data(data)
    return {"ok": True, "prospects": data["prospects"]}


@app.route("/price-adaptator/prospects/<prospect_id>", methods=["DELETE"])
def price_adaptator_delete_prospect(prospect_id):
    data = load_price_adaptator_data()
    prospects = data.get("prospects", [])
    updated = [prospect for prospect in prospects if prospect.get("id") != prospect_id]
    if len(updated) == len(prospects):
        return {"ok": False, "error": "Prospect introuvable"}, 404
    data["prospects"] = updated
    save_price_adaptator_data(data)
    return {"ok": True, "prospects": data["prospects"]}


@app.route("/price-adaptator/prospects", methods=["DELETE"])
def price_adaptator_clear_prospects():
    data = load_price_adaptator_data()
    data["prospects"] = []
    save_price_adaptator_data(data)
    return {"ok": True, "prospects": data["prospects"]}


@app.route("/price-adaptator/import", methods=["POST"])
def price_adaptator_import():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return {"ok": False, "error": "Fichier Excel manquant"}, 400

    try:
        from openpyxl import load_workbook
    except ImportError:
        return {"ok": False, "error": "La bibliothèque openpyxl est manquante"}, 500

    try:
        workbook = load_workbook(filename=BytesIO(upload.read()), data_only=True)
    except Exception:
        return {"ok": False, "error": "Impossible de lire le fichier Excel"}, 400

    sheet = workbook.active
    data = load_price_adaptator_data()
    prospects = data.get("prospects", [])

    existing_emails = {p.get("email", "").strip().lower() for p in prospects if p.get("email")}
    existing_phones = set()
    existing_names = set()
    for prospect in prospects:
        normalized_phone = normalize_phone_number((prospect.get("telephone") or "").strip())
        if normalized_phone:
            existing_phones.add(normalized_phone)
        nom = normalize_price_adaptator_nom(prospect.get("nom")).lower()
        prenom = normalize_price_adaptator_prenom(prospect.get("prenom")).lower()
        formation = (prospect.get("formation") or "").strip()
        if nom and prenom and formation:
            existing_names.add((nom, prenom, formation))

    added_prospects = []
    seen_emails = set()
    seen_phones = set()
    seen_names = set()
    skipped = 0
    errors = []

    def normalize_import_phone(raw_value):
        if raw_value is None:
            return ""
        value = str(raw_value).strip()
        if not value:
            return ""
        if value.startswith("+") or value.startswith("00") or value.startswith("0"):
            return value
        return f"0{value}"

    for idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        values = list(row[:6]) if row else []
        values += [None] * (6 - len(values))
        formation_raw, nom, prenom, cpf, email, telephone = values
        if not any([formation_raw, nom, prenom, cpf, email, telephone]):
            continue

        formation = normalize_price_adaptator_formation(formation_raw)
        if not formation:
            errors.append(f"Ligne {idx}: formation invalide")
            continue

        nom_value = normalize_price_adaptator_nom(nom)
        prenom_value = normalize_price_adaptator_prenom(prenom)
        if not nom_value or not prenom_value:
            errors.append(f"Ligne {idx}: nom/prénom manquants")
            continue

        if cpf is None or (isinstance(cpf, str) and not cpf.strip()):
            cpf_value = 0.0
        else:
            try:
                cpf_value = float(cpf)
                if cpf_value < 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"Ligne {idx}: montant CPF invalide")
                continue
        formation_price = PRICE_ADAPTATOR_FORMATION_PRICES.get(formation)
        if formation_price is not None and cpf_value > formation_price:
            skipped += 1
            errors.append(
                f"Ligne {idx}: montant CPF supérieur au montant de la formation"
            )
            continue

        email_value = str(email).strip() if email is not None else ""
        email_key = email_value.lower() if email_value else ""
        telephone_value = normalize_import_phone(telephone)
        phone_key = normalize_phone_number(telephone_value) or ""

        name_key = (nom_value.lower(), prenom_value.lower(), formation)

        if (
            (email_key and (email_key in existing_emails or email_key in seen_emails))
            or (phone_key and (phone_key in existing_phones or phone_key in seen_phones))
            or (name_key in existing_names or name_key in seen_names)
        ):
            skipped += 1
            errors.append(f"Ligne {idx}: prospect déjà existant")
            continue

        prospect = {
            "id": str(uuid.uuid4()),
            "nom": nom_value,
            "prenom": prenom_value,
            "cpf": cpf_value,
            "email": email_value,
            "telephone": telephone_value,
            "formation": formation,
            "sent": False,
            "sentAt": None,
            "proposed_price": None,
            "last_error": None,
            "last_attempt_at": None,
            "created_at": datetime.now().isoformat(),
        }
        added_prospects.append(prospect)
        if email_key:
            seen_emails.add(email_key)
        if phone_key:
            seen_phones.add(phone_key)
        seen_names.add(name_key)

    if added_prospects:
        data["prospects"] = added_prospects[::-1] + prospects
        save_price_adaptator_data(data)

    return {
        "ok": True,
        "added": len(added_prospects),
        "skipped": skipped,
        "errors": errors,
        "prospects": data.get("prospects", prospects),
    }


@app.route("/price-adaptator/dates", methods=["POST"])
def price_adaptator_save_dates():
    payload = request.get_json(silent=True) or {}
    dates = payload.get("dates", {})
    data = load_price_adaptator_data()
    cleaned = {}
    for formation, range_data in (dates or {}).items():
        if not isinstance(range_data, dict):
            continue
        cleaned[formation] = {
            "start": range_data.get("start"),
            "end": range_data.get("end"),
            "discount": normalize_price_adaptator_discount(range_data.get("discount")),
        }
    data["dates"] = cleaned
    save_price_adaptator_data(data)
    return {"ok": True, "dates": data["dates"]}


@app.route("/price-adaptator/prospects/<prospect_id>/proposal", methods=["POST"])
def price_adaptator_save_proposal(prospect_id):
    payload = request.get_json(silent=True) or {}
    price = payload.get("price")

    if price is None:
        return {"ok": False, "error": "Prix manquant"}, 400

    try:
        price_value = float(price)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Prix invalide"}, 400

    data = load_price_adaptator_data()
    prospect = next((item for item in data.get("prospects", []) if item.get("id") == prospect_id), None)
    if not prospect:
        return {"ok": False, "error": "Prospect introuvable"}, 404

    price_value = normalize_price_adaptator_proposed_price(price_value)
    prospect["proposed_price"] = price_value
    save_price_adaptator_data(data)

    return {"ok": True, "prospects": data.get("prospects", [])}


@app.route("/price-adaptator/send", methods=["POST"])
def price_adaptator_send():
    payload = request.get_json(silent=True) or {}
    price = payload.get("price")
    prospect_id = payload.get("prospect_id")

    if price is None:
        return {"ok": False, "error": "Prix manquant"}, 400

    try:
        price_value = float(price)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Prix invalide"}, 400

    data = load_price_adaptator_data()
    prospect = next((item for item in data.get("prospects", []) if item.get("id") == prospect_id), None)
    if not prospect:
        return {"ok": False, "error": "Prospect introuvable"}, 404

    price_value = normalize_price_adaptator_proposed_price(price_value)
    result = attempt_price_adaptator_send(prospect, data.get("dates"), price_override=price_value)
    prospect["last_attempt_at"] = datetime.now().isoformat()
    prospect["last_error"] = result["email_error"] or result["sms_error"]
    prospect["proposed_price"] = result["price"]
    prospect["manual_sent"] = True
    prospect["manualSentAt"] = datetime.now().isoformat()
    if result["email_sent"] or result["sms_sent"]:
        prospect["sent"] = True
        prospect["sentAt"] = datetime.now().isoformat()
        prospect["last_sent_price"] = result["price"]
    save_price_adaptator_data(data)

    return {
        "ok": True,
        "email_sent": result["email_sent"],
        "sms_sent": result["sms_sent"],
        "email_error": result["email_error"],
        "sms_error": result["sms_error"],
        "prospects": data.get("prospects", []),
    }


@app.route("/price-adaptator/prospects/<prospect_id>/preview")
def price_adaptator_preview(prospect_id):
    data = load_price_adaptator_data()
    prospect = next((item for item in data.get("prospects", []) if item.get("id") == prospect_id), None)
    if not prospect:
        return {"ok": False, "error": "Prospect introuvable"}, 404

    price_override = prospect.get("last_sent_price")
    if price_override is None:
        price_override = prospect.get("proposed_price")
    if price_override is not None:
        price_override = normalize_price_adaptator_proposed_price(price_override)

    message = build_price_adaptator_message(prospect, data.get("dates"), price_override=price_override)
    return {
        "ok": True,
        "subject": message["subject"],
        "html": message["html"],
        "sent_at": prospect.get("sentAt"),
    }


@app.route("/sessions")
def sessions_home():
    data = load_sessions()
    # 🔄 Synchronise automatiquement les étapes manquantes pour chaque session
    for s in data["sessions"]:
        sync_steps(s)
    save_sessions(data)

    today = datetime.now().date()
    active = []
    archived = []

    for s in data["sessions"]:
        end_date = parse_date(s.get("date_fin"))
        is_finished = bool(end_date and end_date.date() < today)
        s["is_finished"] = is_finished

        if s.get("archived") or is_finished:
            archived.append(s)
        else:
            active.append(s)

    for s in data["sessions"]:
        s["color"] = FORMATION_COLORS.get(s["formation"], "#555")

    # --- DEBUG existant ---
    print("\n=== DEBUG SESSIONS ===")
    for s in data["sessions"]:
        print(f"\nSession: {s['formation']} ({s['date_debut']} → {s['date_exam']})")
        for i, step in enumerate(s["steps"]):
            st, dl = status_for_step(i, s)
            if dl:
                print(f" - {step['name']}: {st} / deadline={dl.strftime('%Y-%m-%d')}")
            else:
                print(f" - {step['name']}: {st} / deadline=N/A")

    # --------- 🧠 On calcule le récap en PYTHON ---------
    recap_map = {}   # { formation: {"late_steps":[(text,days)], "today_steps":[text]} }
    total_late = 0

    # On ne prend que les sessions actives (comme avant)
    for s in active:
        formation = s.get("formation", "—")
        rec = recap_map.setdefault(formation, {"late_steps": [], "today_steps": []})

        for i, step in enumerate(s.get("steps", [])):
            st, dl = status_for_step(i, s)
            # late
            if st == "late" and dl:
                days = max((today - dl.date()).days, 0)
                text = f"[{format_date(s.get('date_debut','—'))}] {step['name']}"
                rec["late_steps"].append((text, days))
                total_late += 1
            # due today
            elif st == "on_time" and dl and dl.date() == today:
                text = f"[{format_date(s.get('date_debut','—'))}] {step['name']}"
                rec["today_steps"].append(text)

    # On transforme en liste triée par nom de formation pour le template
    recap_data = []
    for formation, payload in sorted(recap_map.items(), key=lambda x: x[0]):
        # trier les retards par nb de jours décroissant (les pires d'abord)
        payload["late_steps"].sort(key=lambda t: t[1], reverse=True)
        recap_data.append((formation, payload["late_steps"], payload["today_steps"]))

    return render_template(
        "sessions.html",
        title="Gestion des sessions",
        active_sessions=active,
        archived_sessions=archived,
        status_for_step=status_for_step_jinja,  # garde pour le détail
        now=datetime.now,
        # 👇 nouveaux paramètres pour le récap déjà prêt
        recap_data=recap_data,
        total_late=total_late,
        formations=[f for f, *_ in recap_data],
    )



@app.route("/sessions/create", methods=["POST"])
def create_session():
    formation = request.form.get("formation","").upper().strip()
    date_debut = request.form.get("date_debut","").strip()
    date_fin = request.form.get("date_fin","").strip()
    date_exam = request.form.get("date_exam","").strip()
    if formation not in FORMATION_COLORS:
        flash("Formation invalide.","error")
        return redirect(url_for("sessions_home"))
    sid = str(uuid.uuid4())[:8]
    session = {
        "id": sid,
        "formation": formation,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "date_exam": date_exam,
        "color": FORMATION_COLORS.get(formation,"#555"),
        "steps": default_steps_for(formation),
        "archived": False,
        "jurys": [],
        "jury_notification_status": "to_notify",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    data = load_sessions()
    data["sessions"].append(session)
    save_sessions(data)
    return redirect(url_for("session_detail", sid=sid))

@app.route("/sessions/<sid>")
def session_detail(sid):
    # --- 🔐 Vérification accès préfecture si ?key= est présent ---
    public_key = request.args.get("key")

    PREF_EMAIL = os.getenv("PREF_EMAIL")
    PREF_PASSWORD = os.getenv("PREF_PASSWORD")

    if public_key:
        expected = f"{PREF_EMAIL}:{PREF_PASSWORD}"
        encoded = base64.b64encode(expected.encode()).decode()

        if public_key != encoded:
            abort(403)  # accès refusé

    # --- 🔧 Chargement session ---
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)

    ensure_jury_defaults(session)
    ensure_global_jury_defaults(data)
    sync_global_jurys(data)
    sync_steps(session)
    save_sessions(data)

    statuses = []
    for i in range(len(session["steps"])):
        st, dl = status_for_step(i, session)
        statuses.append({"status": st, "deadline": (dl.strftime("%Y-%m-%d") if dl else None)})

    order = sorted(
        range(len(session["steps"])),
        key=lambda i: deadline_for(i, session) or datetime.max
    )

    auto_archive_if_all_done(session)
    save_sessions(data)

    return render_template(
        "session_detail.html",
        title=f"{session['formation']} — Détail",
        s=session,
        global_jurys=data.get("jurys", []),
        session_jurys_by_id={j.get("id"): j for j in session.get("jurys", [])},
        statuses=statuses,
        order=order,
        now=datetime.now,
        planning_pdf=session.get("planning_pdf")
        
    )


@app.route("/sessions/<sid>/jury/add", methods=["POST"])
def add_jury(sid):
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)
    ensure_jury_defaults(session)
    ensure_global_jury_defaults(data)
    sync_global_jurys(data)
    nom = request.form.get("nom", "").strip()
    prenom = request.form.get("prenom", "").strip()
    email = request.form.get("email", "").strip()
    telephone = request.form.get("telephone", "").strip()
    if not nom or not prenom:
        flash("Nom et prénom du jury requis.", "error")
        return redirect(url_for("session_detail", sid=sid))
    existing_global = find_global_jury_by_email(data, email)
    if existing_global:
        existing_global.update({
            "nom": nom or existing_global.get("nom", ""),
            "prenom": prenom or existing_global.get("prenom", ""),
            "email": email or existing_global.get("email", ""),
            "telephone": telephone or existing_global.get("telephone", ""),
        })
        jury_id = existing_global["id"]
    else:
        jury_id = str(uuid.uuid4())[:8]
        data["jurys"].append({
            "id": jury_id,
            "nom": nom,
            "prenom": prenom,
            "email": email,
            "telephone": telephone,
        })
    if any(j.get("id") == jury_id for j in session["jurys"]):
        flash("Ce jury est déjà associé à la session.", "info")
        save_sessions(data)
        return redirect(url_for("session_detail", sid=sid))
    session["jurys"].append({
        "id": jury_id,
        "nom": nom,
        "prenom": prenom,
        "email": email,
        "telephone": telephone,
        "status": "pending",
        "token": str(uuid.uuid4()),
        "notified_at": None,
        "reminded_at": None,
    })
    save_sessions(data)
    flash("Jury ajouté.", "success")
    return redirect(url_for("session_detail", sid=sid))


@app.route("/sessions/<sid>/jury/notify", methods=["POST"])
def notify_jury(sid):
    print("🔥 HIT notify_jury", sid, dict(request.form.lists()))
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)
    ensure_jury_defaults(session)
    ensure_global_jury_defaults(data)
    sync_global_jurys(data)
    selected_ids = request.form.getlist("jury_ids")
    logger.info("[jury notify] Déclenchement", extra={"sid": sid, "selected_ids": selected_ids})
    if not selected_ids:
        flash("Sélectionnez au moins un jury à notifier.", "error")
        return redirect(url_for("session_detail", sid=sid))
    base_url = request.url_root.rstrip("/")
    logger.info("[jury notify] base_url=%s", base_url)
    results = []
    any_sent = False
    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_jurys_by_id = {j.get("id"): j for j in session.get("jurys", [])}
    for jury_id in selected_ids:
        jury = session_jurys_by_id.get(jury_id)
        if not jury:
            global_jury = find_global_jury_by_id(data, jury_id)
            if not global_jury:
                results.append(f"Jury introuvable ({jury_id}).")
                continue
            jury = {
                "id": global_jury.get("id"),
                "nom": global_jury.get("nom", ""),
                "prenom": global_jury.get("prenom", ""),
                "email": global_jury.get("email", ""),
                "telephone": global_jury.get("telephone", ""),
                "status": "pending",
                "token": str(uuid.uuid4()),
                "notified_at": None,
                "reminded_at": None,
            }
            session["jurys"].append(jury)
            session_jurys_by_id[jury_id] = jury
        if jury.get("status") in ("present", "absent"):
            results.append(f"{jury.get('prenom','')} {jury.get('nom','')}: déjà répondu")
            continue
        logger.info(
            "[jury notify] Tentative",
            extra={
                "jid": jury.get("id"),
                "email_set": bool(jury.get("email")),
                "phone_set": bool(jury.get("telephone")),
            },
        )
        token = jury.get("token") or str(uuid.uuid4())
        jury["token"] = token
        yes_url = f"{base_url}{url_for('jury_response', sid=sid, jid=jury['id'], response='present')}?token={token}"
        no_url = f"{base_url}{url_for('jury_response', sid=sid, jid=jury['id'], response='absent')}?token={token}"
        email_ok, email_msg = send_jury_invitation_email(session, jury, yes_url, no_url)
        sms_ok, sms_msg = send_jury_sms(session, jury, yes_url, no_url)
        results.append(f"{jury.get('prenom','')} {jury.get('nom','')}: {email_msg} / {sms_msg}")
        logger.info(
            "[jury notify] Résultat email=%s sms=%s",
            email_msg,
            sms_msg,
        )
        if email_ok or sms_ok:
            any_sent = True
        jury["status"] = "pending"
        jury["notified_at"] = now_txt if email_ok or sms_ok else jury.get("notified_at")
    if any_sent:
        session["jury_notification_status"] = "notified"
    save_sessions(data)
    if results:
        flash_message = " | ".join(results)
        if any_sent:
            flash("Notifications envoyées. " + flash_message, "success")
        else:
            flash("Aucune notification envoyée. " + flash_message, "error")
    return redirect(url_for("session_detail", sid=sid))


@app.route("/sessions/<sid>/jury/<jid>/delete", methods=["POST"])
def delete_jury(sid, jid):
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)
    ensure_jury_defaults(session)
    before = len(session["jurys"])
    session["jurys"] = [j for j in session["jurys"] if j.get("id") != jid]
    after = len(session["jurys"])
    save_sessions(data)
    if before == after:
        flash("Jury introuvable.", "error")
    else:
        flash("Jury supprimé.", "success")
    return redirect(url_for("session_detail", sid=sid))


@app.route("/jury-response/<sid>/<jid>/<response>")
def jury_response(sid, jid, response):
    token = request.args.get("token", "")
    if response not in ("present", "absent"):
        abort(400)
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)
    ensure_jury_defaults(session)
    jury = next((j for j in session["jurys"] if j.get("id") == jid), None)
    if not jury or jury.get("token") != token:
        abort(403)
    already_responded = jury.get("status") in ("present", "absent")
    previous_status = jury.get("status")
    if not already_responded:
        jury["status"] = response
        save_sessions(data)
    return render_template(
        "jury_response.html",
        title="Réponse jury",
        response=previous_status if already_responded else response,
        already_responded=already_responded,
        jury=jury,
        session=session
    )


# ------------------------------------------------------------
# 🔐 Route spéciale préfecture : accès en lecture seule
# ------------------------------------------------------------
@app.route("/prefecture/session/<sid>")
@pref_auth_required
def prefecture_session(sid):
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)

    # recalcul des statuts
    statuses = []
    for i in range(len(session["steps"])):
        st, dl = status_for_step(i, session)
        statuses.append({
            "status": st,
            "deadline": (dl.strftime("%Y-%m-%d") if dl else None)
        })

    order = sorted(
        range(len(session["steps"])),
        key=lambda i: deadline_for(i, session) or datetime.max
    )

    # page dédiée "prefecture_session.html"
    return render_template(
        "prefecture_session.html",
        title=f"Dossier session — Préfecture",
        s=session,
        statuses=statuses,
        order=order,
        now=datetime.now
    )

@app.route("/formateurs/<fid>/edit", methods=["GET", "POST"])
def edit_formateur(fid):
    formateurs = load_formateurs()

    formateur = next((f for f in formateurs if f["id"] == fid), None)
    if not formateur:
        abort(404)

    if request.method == "POST":
        formateur["nom"] = request.form.get("nom", "").strip()
        formateur["prenom"] = request.form.get("prenom", "").strip()
        formateur["email"] = request.form.get("email", "").strip()
        formateur["telephone"] = request.form.get("telephone", "").strip()

        save_formateurs(formateurs)
        return redirect(url_for("formateurs_home"))

    return render_template("edit_formateur.html", formateur=formateur)



@app.route("/sessions/<sid>/edit", methods=["GET","POST"])
def edit_session(sid):
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)
    if request.method == "POST":
        session["date_debut"] = request.form.get("date_debut","").strip()
        session["date_fin"] = request.form.get("date_fin","").strip()
        session["date_exam"] = request.form.get("date_exam","").strip()
        save_sessions(data)
        flash("Session mise à jour.","ok")
        return redirect(url_for("session_detail", sid=sid))
    return render_template("session_edit.html", s=session)

@app.route("/sessions/<sid>/toggle_step", methods=["POST"])
def toggle_step(sid):
    idx = int(request.form.get("index","-1"))
    data = load_sessions()
    session = find_session(data, sid)
    if not session or idx<0 or idx>=len(session["steps"]):
        abort(400)
    step = session["steps"][idx]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    step["done"] = not step["done"]
    step["done_at"] = now if step["done"] else None
    auto_archive_if_all_done(session)
    save_sessions(data)
    return redirect(url_for("session_detail", sid=sid) + f"#step{idx}")

@app.route("/sessions/<sid>/update_date", methods=["POST"])
def update_step_date(sid):
    """Permet de modifier la date fixe d'une étape dans la session GENERAL et la sauvegarder."""
    idx = int(request.form.get("index", "-1"))
    new_date = request.form.get("new_date", "").strip()
    data = load_sessions()
    session = find_session(data, sid)
    if not session or idx < 0 or idx >= len(session["steps"]):
        abort(400)

    if session.get("formation") != "GENERAL":
        flash("❌ Modification de date réservée à la session GENERAL.", "error")
        return redirect(url_for("session_detail", sid=sid))

    try:
        # ✅ On crée un champ 'custom_date' pour cette étape
        session["steps"][idx]["custom_date"] = new_date
        save_sessions(data)
        flash(f"✅ Date mise à jour pour « {session['steps'][idx]['name']} »", "ok")
    except Exception as e:
        flash(f"❌ Erreur modification date : {e}", "error")

    return redirect(url_for("session_detail", sid=sid))


@app.route("/sessions/<sid>/rename", methods=["POST"])
def rename_session(sid):
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        return {"ok": False, "error": "Session introuvable"}, 404

    payload = request.get_json(silent=True) or {}
    raw_name = payload.get("name", request.form.get("name", ""))
    name = (raw_name or "").strip()

    if not name:
        return {"ok": False, "error": "Le nom ne peut pas être vide."}, 400
    if len(name) > 80:
        return {"ok": False, "error": "Le nom est trop long (80 caractères max)."}, 400

    session["display_name"] = name
    save_sessions(data)
    return {"ok": True, "name": name}


@app.route("/sessions/<sid>/delete", methods=["POST"])
def delete_session(sid):
    data = load_sessions()
    data["sessions"] = [s for s in data["sessions"] if s["id"]!=sid]
    save_sessions(data)
    flash("Session supprimée.","ok")
    return redirect(url_for("sessions_home"))

@app.post("/sessions/<sid>/planning/upload")
def upload_planning_pdf(sid):
    f = request.files.get("planning_pdf")
    if not f or f.filename == "":
        flash("❌ Aucun fichier reçu.", "error")
        return redirect(url_for("session_detail", sid=sid))

    # sécurité : on force PDF
    if not f.filename.lower().endswith(".pdf"):
        flash("❌ Le fichier doit être un PDF.", "error")
        return redirect(url_for("session_detail", sid=sid))

    saved_name = f"planning_session_{sid}.pdf"
    path = os.path.join(PLANNING_DIR, saved_name)
    f.save(path)

    set_planning_for_session(sid, saved_name)
    flash("✅ Planning PDF enregistré.", "ok")
    return redirect(url_for("session_detail", sid=sid))


@app.get("/sessions/<sid>/planning/view")
def view_planning_pdf(sid):
    name = get_planning_for_session(sid)
    if not name:
        abort(404)

    path = os.path.join(PLANNING_DIR, name)
    if not os.path.exists(path):
        abort(404)

    return send_file(path, mimetype="application/pdf", as_attachment=False)


@app.get("/sessions/<sid>/planning/download")
def download_planning_pdf(sid):
    name = get_planning_for_session(sid)
    if not name:
        abort(404)

    path = os.path.join(PLANNING_DIR, name)
    if not os.path.exists(path):
        abort(404)

    return send_file(path, mimetype="application/pdf", as_attachment=True, download_name=name)


@app.route("/healthz")
def healthz():
    return "ok"

@app.route("/cron-check")
def cron_check():
    data = load_sessions()
    for session in data["sessions"]:
        auto_archive_if_all_done(session)
    reminded = send_jury_reminders(data, request.url_root.rstrip("/"))
    expired_alerts = send_formateur_expiration_alerts()
    save_sessions(data)
    message = "Cron check terminé"
    if reminded:
        message = f"{message} | Rappels jury envoyés: {', '.join(reminded)}"
    if expired_alerts:
        message = f"{message} | Alertes expiration formateurs: {expired_alerts}"
    return message, 200

@app.route("/cron-daily-summary")
def cron_daily_summary():
    send_daily_overdue_summary()
    return "Mail récapitulatif envoyé", 200

# ------------------------------------------------------------
# ✅ Route publique pour le suivi auto sur la plateforme principale
#    -> renvoie le nombre total d'étapes en retard (toutes sessions actives)
# ------------------------------------------------------------
@app.route("/data.json")
def data_sessions_json():
    try:
        data = load_sessions()
        sessions = data.get("sessions", [])

        today = datetime.now().date()
        total_retards = 0
        details = []  # utile si tu veux diagnostiquer

        for s in sessions:
            if s.get("archived"):
                continue  # on ignore les sessions archivées

            late_steps = []
            for i, step in enumerate(s.get("steps", [])):
                st, dl = status_for_step(i, s)
                if st == "late":
                    total_retards += 1
                    late_steps.append({
                        "name": step.get("name"),
                        "deadline": (dl.strftime("%Y-%m-%d") if dl else None)
                    })

            details.append({
                "id": s.get("id"),
                "formation": s.get("formation"),
                "date_debut": s.get("date_debut"),
                "date_exam": s.get("date_exam"),
                "retards": len(late_steps),
                "late_steps": late_steps
            })

        payload = {
            "retards": total_retards,   # 👉 c'est cette clé que l'index lit pour afficher "XX étapes en retard" / "Dans les temps"
            "sessions": details
        }

        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
        return json.dumps(payload, ensure_ascii=False), 200, headers

    except Exception as e:
        print("Erreur /data.json (sessions):", e)
        return json.dumps({"retards": -1, "error": str(e)}), 500, {
            "Access-Control-Allow-Origin": "*"
        }

@app.route("/tz-test")
def tz_test():
    from datetime import datetime
    import time
    return f"Serveur : {datetime.now()}<br>Heure système : {time.tzname}"

# ------------------------------------------------------------
# 📦 GESTION DES DOTATIONS
# ------------------------------------------------------------

DOTATIONS_FILE = os.path.join(DATA_DIR, "dotations.json")

def load_dotations():
    if os.path.exists(DOTATIONS_FILE):
        try:
            with open(DOTATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_dotations(data):
    with open(DOTATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ✉️ Fonction d’envoi d’email (réutilise la conf SMTP)
def send_email(to, subject, body):
    if not FROM_EMAIL or not EMAIL_PASSWORD:
        print("⚠️ Email non configuré")
        return
    msg = MIMEText(body, "html", "utf-8")
    msg["From"] = FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls()
            s.login(FROM_EMAIL, EMAIL_PASSWORD)
            s.sendmail(FROM_EMAIL, [to], msg.as_string())
        print(f"✅ Mail envoyé à {to}")
    except Exception as e:
        print("❌ Erreur envoi mail dotation :", e)


def send_price_adaptator_email(to, subject, html):
    smtp_config = get_smtp_config()
    if not smtp_config["login"] or not smtp_config["password"]:
        return False, "SMTP non configuré"
    msg = MIMEText(html, "html", "utf-8")
    msg["From"] = smtp_config["from_email"]
    msg["To"] = to
    msg["Cc"] = "clement@integraleacademy.com"
    msg["Subject"] = subject
    try:
        with smtplib.SMTP(smtp_config["server"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["login"], smtp_config["password"])
            server.sendmail(
                smtp_config["from_email"],
                [to, "clement@integraleacademy.com"],
                msg.as_string(),
            )
        return True, None
    except Exception as e:
        print("❌ Erreur envoi mail price adaptator :", e)
        return False, str(e)


def send_price_adaptator_sms(phone, message):
    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        return False, "Téléphone au format international requis (ex: +336...)"

    # ✅ Utilise Brevo comme pour les SMS jury
    if BREVO_API_KEY and BREVO_SMS_SENDER:
        print("[price sms] Envoi via Brevo API", {"to": normalized_phone, "sender": BREVO_SMS_SENDER})

        payload = json.dumps({
            "sender": BREVO_SMS_SENDER,
            "recipient": normalized_phone,
            "content": message,
            "type": "transactional",
        }).encode("utf-8")

        req = urllib.request.Request("https://api.brevo.com/v3/transactionalSMS/sms")
        req.add_header("Content-Type", "application/json")
        req.add_header("api-key", BREVO_API_KEY)

        try:
            with urllib.request.urlopen(req, data=payload, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                print("[price sms] Brevo response", resp.status, body)
                if 200 <= resp.status < 300:
                    return True, None
                return False, f"Brevo SMS erreur {resp.status}: {body}"

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print("[price sms] Brevo HTTPError", e.code, body)
            return False, f"Brevo HTTP {e.code}: {body}"

        except Exception as e:
            print("[price sms] Brevo exception", repr(e))
            return False, str(e)

    return False, "SMS non configuré (BREVO_API_KEY / BREVO_SMS_SENDER manquants)"


@app.route("/dotations")
def dotations_home():
    data = load_dotations()
    return render_template("dotations.html", title="Gestion des dotations", dotations=data)


@app.route("/dotations/add", methods=["POST"])
def add_dotation():
    data = load_dotations()
    item = {
        "id": str(uuid.uuid4())[:8],
        "nom": request.form.get("nom", "").strip(),
        "prenom": request.form.get("prenom", "").strip(),
        "email": request.form.get("email", "").strip(),
        "ipad": request.form.get("ipad", "").strip(),
        "badge": request.form.get("badge", "").strip(),
        "date_remise": request.form.get("date_remise", "").strip(),
        "statut": "Dotation à distribuer",
        "commentaire": request.form.get("commentaire", "").strip(),
    }
    data.append(item)
    save_dotations(data)
    flash("Dotation ajoutée avec succès.", "ok")
    return redirect(url_for("dotations_home"))


@app.route("/dotations/<id>/delete", methods=["POST"])
def delete_dotation(id):
    data = load_dotations()
    data = [d for d in data if d["id"] != id]
    save_dotations(data)
    flash("Dotation supprimée.", "ok")
    return redirect(url_for("dotations_home"))


@app.route("/dotations/<id>/edit", methods=["POST"])
def edit_dotation(id):
    data = load_dotations()
    for d in data:
        if d["id"] == id:
            d["nom"] = request.form.get("nom", d["nom"])
            d["prenom"] = request.form.get("prenom", d["prenom"])
            d["email"] = request.form.get("email", d["email"])
            d["ipad"] = request.form.get("ipad", d["ipad"])
            d["badge"] = request.form.get("badge", d["badge"])
            d["date_remise"] = request.form.get("date_remise", d["date_remise"])
            d["commentaire"] = request.form.get("commentaire", d["commentaire"])
            break
    save_dotations(data)
    flash("Dotation modifiée.", "ok")
    return redirect(url_for("dotations_home"))

@app.route("/dotations/<id>/update_date", methods=["POST"])
def update_date_remise(id):
    data = load_dotations()
    for d in data:
        if d["id"] == id:
            d["date_remise"] = request.form.get("date_remise", d["date_remise"])
            break
    save_dotations(data)
    flash("Date de remise mise à jour.", "ok")
    return redirect(url_for("dotations_home"))

@app.route("/dotations/<id>/rupture", methods=["POST"])
def rupture_contrat(id):
    data = load_dotations()
    for d in data:
        if d["id"] == id:
            d["statut"] = "Dotation non restituée"
            save_dotations(data)
            body = f"""
            Bonjour {d['prenom']},<br><br>

            Suite à la rupture de votre contrat d’apprentissage, nous vous rappelons que vous devez restituer l’ensemble du matériel mis à disposition (iPad, chargeur et badge distributeur) dans un délai de 5 jours, conformément à la convention signée.<br><br>

            Le matériel peut être déposé directement au centre Intégrale Academy (54 chemin du Carreou, 83480 Puget-sur-Argens) ou envoyé par courrier suivi à la même adresse.<br><br>

            L’iPad doit être restitué en parfait état de fonctionnement et sans dégradation.<br>
            En cas de non-restitution ou de matériel dégradé, des pénalités financières pourront être appliquées :<br>
            – 400 € pour l’iPad<br>
            – 20 € pour le chargeur<br>
            – 20 € pour le badge distributeur<br><br>

            Bien cordialement,<br>
            <b>Clément VAILLANT</b><br>
            Directeur général – Intégrale Academy
            """
            send_email(d["email"], "Restitution du matériel – Intégrale Academy", body)
            break
    flash("📩 Mail de rupture envoyé et statut mis à jour.", "ok")
    return redirect(url_for("dotations_home"))


@app.route("/dotations/<id>/badge_fin", methods=["POST"])
def badge_fin(id):
    data = load_dotations()
    for d in data:
        if d["id"] == id:
            d["statut"] = "Dotation non restituée"  # ✅ au lieu de "Dotation restituée"
            save_dotations(data)
            body = f"""
            Bonjour {d['prenom']},<br><br>
            Votre BTS touche à sa fin, nous vous rappelons que vous devez nous restituer le badge distributeur de boissons et snack avant de quitter l'école, conformément à la convention signée.<br><br>
            Vous pouvez le déposer directement au centre Intégrale Academy (54 chemin du Carreou, 83480 Puget-sur-Argens) ou l’envoyer par courrier suivi à la même adresse.<br><br>
            Nous vous remercions par avance pour votre réactivité.<br><br>
            Bien cordialement,<br>
            <b>L’équipe Intégrale Academy</b>
            """
            send_email(d["email"], "Restitution du badge distributeur – Intégrale Academy", body)
            break
    flash("📩 Mail de fin d’études envoyé et statut mis à jour.", "ok")
    return redirect(url_for("dotations_home"))





@app.route("/dotations/<id>/changer_statut", methods=["POST"])
def changer_statut(id):
    nouveau_statut = request.form.get("statut")
    data = load_dotations()
    for d in data:
        if d["id"] == id:
            d["statut"] = nouveau_statut
            break
    save_dotations(data)
    return redirect(url_for("dotations_home"))

# ------------------------------------------------------------
# 👨‍🏫 GESTION DES FORMATEURS (Contrôle formateurs)
# ------------------------------------------------------------

FORMATEURS_FILE = os.path.join(DATA_DIR, "formateurs.json")
FORMATEURS_LOCK = FORMATEURS_FILE + ".lock"
FORMATEUR_FILES_DIR = os.path.join(DATA_DIR, "formateurs_files")
os.makedirs(FORMATEUR_FILES_DIR, exist_ok=True)

DEFAULT_DOC_LABELS = [
    "Badge formateur indépendant",
    "Pièce d’identité",
    "Carte pro formateur",
    "Carte pro APS",
    "Carte pro A3P",
    "Diplôme APS",
    "Diplôme A3P",
    "Numéro NDA",
    "Extrait SIRENE moins de 3 mois",
    "Attestation d’assurance RC PRO",
    "Extrait KBIS moins de 3 mois",
    "DRACAR moins de 3 mois",
    "Diplôme SSIAP 1 à jour",
    "Diplôme SSIAP 2 à jour",
    "Diplôme SSIAP 3 à jour",
    "Carte formateur SST",
    "Attestation prévention des risques terroristes",
    "Attestation événementiel spécifique",
    "Attestation palpation de sécurité",
    "Attestation gestion des conflits",
    "Attestation gestion des conflits dégradés",
    "Diplôme formateur pédagogie",
    "Attestation sur l’honneur CNAPS",
    "Attestation de vigilance URSSAF de moins de 3 mois",
    "Charte qualité du formateur",
    "Attestation vacataire APS Adef",
    "Attestation vacataire A3P Adef",
    "Agrément dirigeant CNAPS (AGD)",
    "Autorisation d’exercice CNAPS",
    "CV à jour",
    "Photo d'identité",
]

def load_formateurs():
    def _read_json(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # 1) Lecture normale
    if os.path.exists(FORMATEURS_FILE):
        try:
            data = _read_json(FORMATEURS_FILE)
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass  # on tentera le backup

    # 2) Tentative restore depuis .bak
    bak_path = FORMATEURS_FILE + ".bak"
    if os.path.exists(bak_path):
        try:
            data = _read_json(bak_path)
            if isinstance(data, list):
                # on restaure le fichier principal
                save_formateurs(data)
                return data
        except Exception:
            pass

    # 3) Dernier recours
    return []



def save_formateurs(data):
    # verrou simple (anti écritures concurrentes)
    start = time.time()
    while os.path.exists(FORMATEURS_LOCK):
        # évite de bloquer à l’infini si un lock “fantôme” reste
        if time.time() - start > 5:
            try:
                os.remove(FORMATEURS_LOCK)
            except Exception:
                break
        time.sleep(0.05)

    # créer le lock
    with open(FORMATEURS_LOCK, "w") as f:
        f.write(str(os.getpid()))

    try:
        # écriture atomique: tmp -> replace
        tmp_path = FORMATEURS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, FORMATEURS_FILE)

        # backup
        bak_path = FORMATEURS_FILE + ".bak"
        try:
            with open(bak_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    finally:
        try:
            os.remove(FORMATEURS_LOCK)
        except Exception:
            pass




def find_formateur(formateurs, fid):
    for f in formateurs:
        if f.get("id") == fid:
            return f
    return None


def build_default_documents():
    docs = []
    for label in DEFAULT_DOC_LABELS:
        docs.append({
            "id": str(uuid.uuid4())[:8],
            "label": label,
            "expiration": "",
            "status": "non_conforme",  # par défaut
            "commentaire": "",
            "attachments": []  # liste de {filename, original_name}
        })
    return docs


def auto_update_document_status(doc):
    """
    Si une date d'expiration est renseignée et dépassée,
    on force le statut à 'non_conforme' (sauf si 'non_concerne').
    """
    if doc.get("status") == "non_concerne":
        return

    exp_str = doc.get("expiration", "").strip()
    if not exp_str:
        return

    dt = parse_date(exp_str)
    if not dt:
        return

    if dt.date() < datetime.now().date():
        doc["status"] = "non_conforme"



# ------------------------------------------------------------
# 🔑🟦 ÉTAT COMPLET DES CLÉS & BADGES
# ------------------------------------------------------------
def get_etat_cles_badges(formateurs, total_cles=15, total_badges=15):

    # --- Clés ---
    etat_cles = {
        i: {
            "type": TYPES_CLES.get(i, "Inconnu"),
            "attribue_a": "Libre"
        }
        for i in range(1, total_cles + 1)
    }

    # --- Badges ---
    etat_badges = {
        i: {
            "type": "Badge portail",
            "attribue_a": "Libre"
        }
        for i in range(1, total_badges + 1)
    }

    for f in formateurs:
        nom_prenom = f"{f.get('prenom','')} {f.get('nom','').upper()}".strip()

        # ---- CLÉ ----
        cle = f.get("cle", {})
        num_c = str(cle.get("numero", "")).strip()

        # 🔥 Normalisation : True / "true" / "1" / "on"
        attrib_c = str(cle.get("attribuee", "")).lower() in ("true", "1", "yes", "on")

        if attrib_c and num_c.isdigit():
            num = int(num_c)
            if num in etat_cles:
                nom_custom = cle.get("custom_nom", "").strip()
                nom_formateur = nom_prenom
                etat_cles[num]["attribue_a"] = nom_custom if nom_custom else nom_formateur

        # ---- BADGE ----
        badge = f.get("badge", {})
        num_b = str(badge.get("numero", "")).strip()

        attrib_b = str(badge.get("attribue", "")).lower() in ("true", "1", "yes", "on")

        if attrib_b and num_b.isdigit():
            num = int(num_b)
            if num in etat_badges:
                etat_badges[num]["attribue_a"] = nom_prenom

    return etat_cles, etat_badges



# --- CONFIG TYPES DE CLES ---
TYPES_CLES = {
    1: "PASS GENERAL",
    2: "PASS GENERAL",
    3: "PASS GENERAL",

    4: "PASS PARTIEL",
    5: "PASS PARTIEL",
    6: "PASS PARTIEL",      # 🔥 changement demandé

    7: "APPARTEMENT",       # 🔥 renommage

    8: "VIOLET",
    9: "VIOLET",
    10: "VIOLET",
    11: "VIOLET",
    12: "VIOLET",
    13: "VIOLET",
    14: "VIOLET",
    15: "VIOLET",
    16: "VIOLET"            # 🔥 ajout de la 16e clé
}



@app.route("/formateurs")
def formateurs_home():
    formateurs = load_formateurs()

    for f in formateurs:
        if "cle" not in f:
            f["cle"] = {
                "attribuee": False,
                "numero": "",
                "statut": "non_attribuee"
            }

        if "badge" not in f:
            f["badge"] = {
                "attribue": False,
                "numero": "",
                "statut": "non_attribue"
            }

        # ✅ conformité + simple indicateur "docs à contrôler"
        total = 0
        conformes = 0
        a_controler = False

        for doc in f.get("documents", []):
            auto_update_document_status(doc)

            status = doc.get("status", "non_conforme")
            if status != "non_concerne":
                total += 1
                if status == "conforme":
                    conformes += 1
                if status == "a_controler":
                    a_controler = True

        f["conformite"] = {"conformes": conformes, "total": total}
        f["a_controler"] = a_controler


    # ===== EXTRACTION DES CLÉS & BADGES =====
    liste_cles = []
    liste_badges = []

    for f in formateurs:
        # --- Clés ---
        cle = f.get("cle", {})
        num = cle.get("numero", "").strip()
        if cle.get("attribuee") and num.isdigit():
            liste_cles.append(int(num))

        # --- Badges ---
        badge = f.get("badge", {})
        num_b = badge.get("numero", "").strip()
        if badge.get("attribue") and num_b.isdigit():
            liste_badges.append(int(num_b))

    liste_cles = sorted(liste_cles)
    liste_badges = sorted(liste_badges)

    # ===== PLAGES TOTALES =====
    total_cles = list(range(1, 17))  # Clés 1 → 16
    total_badges = list(range(1, 16))     # Badges 1 → 15

    # ===== NUMÉROS DISPONIBLES =====
    cles_dispos = [n for n in total_cles if n not in liste_cles]
    badges_dispos = [n for n in total_badges if n not in liste_badges]

    # ===== ÉTAT COMPLET CLÉS & BADGES =====
    etat_cles, etat_badges = get_etat_cles_badges(formateurs, 16, 15)


    return render_template(
        "formateurs.html",
        title="Contrôle formateurs",
        formateurs=formateurs,
        liste_cles=liste_cles,
        liste_badges=liste_badges,
        cles_dispos=cles_dispos,
        badges_dispos=badges_dispos,
        etat_cles=etat_cles,       # 👈 ajouté
        etat_badges=etat_badges   # 👈 ajouté
    )





@app.route("/formateurs/add", methods=["POST"])
def add_formateur():
    formateurs = load_formateurs()
    fid = str(uuid.uuid4())[:8]

    formateur = {
        "id": fid,
        "nom": request.form.get("nom", "").strip(),
        "prenom": request.form.get("prenom", "").strip(),
        "email": request.form.get("email", "").strip(),
        "telephone": request.form.get("telephone", "").strip(),

        "cle": {
            "attribuee": False,
            "numero": "",
            "statut": "non_attribuee"
        },

        "badge": {
            "attribue": False,
            "numero": "",
            "statut": "non_attribue"
        },

        "documents": build_default_documents()
    }

    formateurs.append(formateur)
    save_formateurs(formateurs)
    return redirect(url_for("formateur_detail", fid=fid))



@app.route("/formateurs/<fid>/cle/update", methods=["POST"])
def update_formateur_cle(fid):
    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        return {"ok": False}, 404

    cle = formateur.setdefault("cle", {})

    cle["attribuee"] = request.form.get("attribuee") == "true"
    cle["numero"] = request.form.get("numero", "").strip()
    cle["statut"] = request.form.get("statut", "non_attribuee")

    # 🆕 AJOUT — nom libre si la clé est donnée à quelqu’un qui n’est pas formateur
    cle["custom_nom"] = request.form.get("custom_nom", "").strip()

    save_formateurs(formateurs)
    return {"ok": True}


@app.route("/formateurs/<fid>/badge/update", methods=["POST"])
def update_formateur_badge(fid):
    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        return {"ok": False}, 404

    badge = formateur.setdefault("badge", {})

    badge["attribue"] = request.form.get("attribue") == "true"
    badge["numero"] = request.form.get("numero", "").strip()
    badge["statut"] = request.form.get("statut", "non_attribue")

    save_formateurs(formateurs)
    return {"ok": True}



@app.route("/formateurs/<fid>")
def formateur_detail(fid):
    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        abort(404)

    # mise à jour auto des statuts selon la date d'expiration
    for doc in formateur.get("documents", []):
        auto_update_document_status(doc)
    save_formateurs(formateurs)

    # 🔑🟦 RÉCUPÉRER TOUTES LES CLÉS / BADGES EXISTANTS
    etat_cles, etat_badges = get_etat_cles_badges(formateurs, 16, 15)

    return render_template(
        "formateur_detail.html",
        title=f"Contrôle formateur — {formateur.get('prenom', '')} {formateur.get('nom', '').upper()}",
        formateur=formateur,
        etat_cles=etat_cles,       # 👈 indispensable
        etat_badges=etat_badges    # 👈 indispensable
    )



@app.route("/formateurs/<fid>/delete", methods=["POST"])
def delete_formateur(fid):
    formateurs = load_formateurs()
    formateurs = [f for f in formateurs if f.get("id") != fid]
    save_formateurs(formateurs)
    flash("Formateur supprimé.", "ok")
    return redirect(url_for("formateurs_home"))


@app.route("/formateurs/<fid>/documents/add", methods=["POST"])
def add_formateur_document(fid):
    label = request.form.get("label", "").strip()
    if not label:
        return redirect(url_for("formateur_detail", fid=fid))

    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        abort(404)

    doc = {
        "id": str(uuid.uuid4())[:8],
        "label": label,
        "expiration": "",
        "status": "non_conforme",
        "commentaire": "",
        "attachments": []
    }
    formateur.setdefault("documents", []).append(doc)
    save_formateurs(formateurs)
    return redirect(url_for("formateur_detail", fid=fid))


@app.route("/formateurs/<fid>/documents/<doc_id>/update", methods=["POST"])
def update_formateur_document(fid, doc_id):
    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        return {"ok": False, "error": "Formateur introuvable"}, 404

    docs = formateur.get("documents", [])
    doc = next((d for d in docs if d.get("id") == doc_id), None)
    if not doc:
        return {"ok": False, "error": "Document introuvable"}, 404

    # champs texte
    if "expiration" in request.form:
        doc["expiration"] = request.form.get("expiration", "").strip()

    if "status" in request.form:
        st = request.form.get("status")
        if st in ("non_concerne", "a_controler", "conforme", "non_conforme"):
            doc["status"] = st


    if "commentaire" in request.form:
        doc["commentaire"] = request.form.get("commentaire", "").strip()

    # pièces jointes
    files = request.files.getlist("piece_jointe")
    if files:
        subdir = os.path.join(FORMATEUR_FILES_DIR, fid, doc_id)
        os.makedirs(subdir, exist_ok=True)
        attachments = doc.setdefault("attachments", [])

        for f in files:
            if not f.filename:
                continue
            original_name = f.filename
            safe_name = secure_filename(original_name)
            stored_name = f"{int(time.time())}_{safe_name}"
            filepath = os.path.join(subdir, stored_name)
            f.save(filepath)
            attachments.append({
                "filename": stored_name,
                "original_name": original_name
            })

    auto_update_document_status(doc)
    save_formateurs(formateurs)

    # ⛔️ PLUS AUCUN REDIRECT
    return {"ok": True}



@app.route("/formateurs/<fid>/documents/<doc_id>/attachments/<filename>")
def download_formateur_attachment(fid, doc_id, filename):
    subdir = os.path.join(FORMATEUR_FILES_DIR, fid, doc_id)
    return send_from_directory(subdir, filename, as_attachment=False)


@app.route(
    "/formateurs/<fid>/documents/<doc_id>/attachments/<filename>/delete",
    methods=["POST"]
)
def delete_formateur_attachment(fid, doc_id, filename):

    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        return {"ok": False}, 404

    doc = next(
        (d for d in formateur.get("documents", [])
         if d.get("id") == doc_id),
        None
    )
    if not doc:
        return {"ok": False}, 404

    # 📁 Suppression fichier physique
    file_path = os.path.join(
        FORMATEUR_FILES_DIR,
        fid,
        doc_id,
        filename
    )
    if os.path.exists(file_path):
        os.remove(file_path)

    # 🧹 Suppression dans le JSON
    doc["attachments"] = [
        a for a in doc.get("attachments", [])
        if a.get("filename") != filename
    ]

    # 🔁 Si plus de PJ → non conforme
    if not doc["attachments"]:
        doc["status"] = "non_conforme"

    save_formateurs(formateurs)

    return {"ok": True}




# ------------------------------------------------------------
# 📊 Route JSON pour les dotations (affichage sur index)
# ------------------------------------------------------------
@app.route("/dotations_data.json")
def dotations_data():
    try:
        data = load_dotations()
        a_distribuer = len([d for d in data if d.get("statut") == "Dotation à distribuer"])
        distribuees = len([d for d in data if d.get("statut") == "Dotation distribuée"])
        non_restituees = len([d for d in data if d.get("statut") == "Dotation non restituée"])
        restituees = len([d for d in data if d.get("statut") == "Dotation restituée"])

        payload = {
            "a_distribuer": a_distribuer,
            "distribuees": distribuees,
            "non_restituees": non_restituees,
            "restituees": restituees
        }

        headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        return json.dumps(payload, ensure_ascii=False), 200, headers
    except Exception as e:
        print("Erreur /dotations_data.json :", e)
        return json.dumps({"error": str(e)}), 500, {"Access-Control-Allow-Origin": "*"}

# ------------------------------------------------------------
# 📊 Route JSON Formateurs (pour tuile dashboard)
# ------------------------------------------------------------
@app.route("/formateurs_data.json")
def formateurs_data():
    try:
        formateurs = load_formateurs()

        total_non_conformes = 0
        total_a_controler = 0

        liste_non_conformes = set()
        liste_a_controler = set()

        for f in formateurs:
            nom_complet = f"{f.get('prenom','')} {f.get('nom','')}".strip()

            has_non_conforme = False
            has_a_controler = False

            for doc in f.get("documents", []):
                auto_update_document_status(doc)
                st = doc.get("status")

                if st == "non_conforme":
                    total_non_conformes += 1
                    has_non_conforme = True

                if st == "a_controler":
                    total_a_controler += 1
                    has_a_controler = True

            if has_non_conforme:
                liste_non_conformes.add(nom_complet)

            if has_a_controler:
                liste_a_controler.add(nom_complet)

        payload = {
            "non_conformes": total_non_conformes,
            "a_controler": total_a_controler,
            "liste_non_conformes": sorted(list(liste_non_conformes)),
            "liste_a_controler": sorted(list(liste_a_controler)),
        }

        headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        return json.dumps(payload, ensure_ascii=False), 200, headers

    except Exception as e:
        print("Erreur /formateurs_data.json :", e)
        return json.dumps({"error": str(e)}), 500, {"Access-Control-Allow-Origin": "*"}


import zipfile
from flask import send_file
from io import BytesIO

@app.route("/formateurs/<fid>/export")
def export_formateur_dossier(fid):
    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        abort(404)

    nom = (formateur.get("nom") or "").upper()
    prenom = (formateur.get("prenom") or "").strip()
    dossier_name = f"{nom} {prenom}".strip()

    # ZIP en mémoire (pas écrit sur le disque)
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for doc in formateur.get("documents", []):
            label = doc.get("label", "Document").strip()

            for att in doc.get("attachments", []):
                filename = att.get("filename")
                original = att.get("original_name")

                if not filename or not original:
                    continue

                file_path = os.path.join(
                    FORMATEUR_FILES_DIR,
                    fid,
                    doc["id"],
                    filename
                )

                if not os.path.exists(file_path):
                    continue

                ext = os.path.splitext(original)[1]
                clean_name = f"{label} {prenom} {nom}{ext}"

                arcname = os.path.join(
                    dossier_name,
                    clean_name
                )

                zipf.write(file_path, arcname)

    zip_buffer.seek(0)

    zip_filename = f"Dossier formateur {prenom} {nom}.zip"

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=zip_filename,
        mimetype="application/zip"
    )

@app.route("/formateurs/<fid>/print")
def print_formateur_dossier(fid):
    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        abort(404)

    # Mise à jour auto des statuts avant impression
    for doc in formateur.get("documents", []):
        auto_update_document_status(doc)

    # Liste des docs non conformes / manquants
    non_conformes = [
        d for d in formateur.get("documents", [])
        if d.get("status") == "non_conforme"
    ]

    return render_template(
        "formateur_print.html",
        title="État du dossier formateur",
        formateur=formateur,
        non_conformes=non_conformes,
        today=datetime.now().strftime("%d/%m/%Y")
    )

import hashlib
import time

def generate_upload_token(fid):
    secret = app.secret_key
    raw = f"{fid}:{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()

def verify_upload_token(fid, token):
    return token == generate_upload_token(fid)

@app.route("/formateurs/<fid>/upload", methods=["GET", "POST"])
def upload_formateur_documents(fid):
    token = request.args.get("token", "")
    if not verify_upload_token(fid, token):
        abort(403)

    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        abort(404)

    # Documents à régulariser
    docs_ko = [
        d for d in formateur.get("documents", [])
        if d.get("status") == "non_conforme"
    ]

    if request.method == "POST":
        doc_id = request.form.get("doc_id")
        files = request.files.getlist("files")

        doc = next((d for d in docs_ko if d["id"] == doc_id), None)
        if not doc:
            abort(400)

        subdir = os.path.join(FORMATEUR_FILES_DIR, fid, doc_id)
        os.makedirs(subdir, exist_ok=True)

        allowed_ext = ["pdf", "png", "jpg", "jpeg"]

        for f in files:
            if not f.filename:
                continue

            # Vérification extension
            ext = f.filename.lower().rsplit(".", 1)[-1]
            if ext not in allowed_ext:
                flash("❌ Seuls les fichiers PDF, PNG, JPG et JPEG sont acceptés.", "error")
                return redirect(request.url)

            safe = secure_filename(f.filename)
            name = f"{int(time.time())}_{safe}"
            f.save(os.path.join(subdir, name))

            doc.setdefault("attachments", []).append({
                "filename": name,
                "original_name": f.filename
            })

        # Après upload → conforme
        doc["status"] = "a_controler"
        save_formateurs(formateurs)
        flash("Document transmis avec succès.", "ok")
        return redirect(request.url)

    return render_template(
        "formateur_upload.html",
        formateur=formateur,
        docs_ko=docs_ko
    )


@app.route("/formateurs/<fid>/send_mail", methods=["POST"])
def send_formateur_relance(fid):
    formateurs = load_formateurs()
    formateur = find_formateur(formateurs, fid)
    if not formateur:
        abort(404)

    # 📌 Documents non conformes avec commentaire
    docs_ko = [
        {
            "label": d["label"],
            "commentaire": d.get("commentaire", "").strip()
        }
        for d in formateur.get("documents", [])
        if d.get("status") == "non_conforme"
    ]

    if not docs_ko:
        flash("Aucun document à relancer.", "ok")
        return redirect(url_for("formateur_detail", fid=fid))

    # 🔗 Génération lien sécurisé pour upload
    token = generate_upload_token(fid)
    link = url_for(
        "upload_formateur_documents",
        fid=fid,
        token=token,
        _external=True
    )

    # ✉️ Contenu du mail avec bouton visible
    body = f"""
Bonjour {formateur.get('prenom')},<br><br>

Votre dossier formateur nécessite quelques mises à jour. Merci de transmettre vos documents via le bouton ci-dessous. 
<b style='color:#d00000;'>Les envois par mail ne sont plus acceptés.</b><br><br>

<div style="text-align:center;margin:25px 0;">
  <a href="{link}" style="
      display:inline-block;
      padding:14px 28px;
      background:#0f62fe;
      color:#ffffff !important;
      font-size:18px;
      font-weight:700;
      border-radius:8px;
      text-decoration:none;
      box-shadow:0 4px 12px rgba(0,0,0,0.18);
  ">
      📁 Déposer mes documents
  </a>
</div>

Voici les éléments à régulariser :<br><br>

<ul style="font-size:15px;line-height:1.5;">
  {''.join(
    f"<li><b>{d['label']}</b>"
    + (f"<br><span style='color:red;font-weight:600;'>⚠️ {d['commentaire']}</span>" if d['commentaire'] else "")
    + "</li><br>"
    for d in docs_ko
  )}
</ul>

Cordialement,<br>
<b>Intégrale Academy</b>
"""


    # 📩 Envoi
    send_email(
        formateur.get("email"),
        "Documents manquants — Dossier formateur",
        body
    )

    # 🕒 Trace de la relance
    formateur["last_relance"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_formateurs(formateurs)

    flash("📧 Mail envoyé au formateur.", "ok")
    return redirect(url_for("formateur_detail", fid=fid))


@app.route("/cle/assign", methods=["POST"])
def assign_cle():
    payload = request.get_json()
    numero = str(payload.get("numero"))
    fid = payload.get("fid")

    formateurs = load_formateurs()

    # 🔄 Retirer cette clé à tous les formateurs
    for f in formateurs:
        cle = f.setdefault("cle", {})
        if cle.get("numero") == numero:
            cle["attribuee"] = False
            cle["numero"] = ""
            cle["statut"] = "non_attribuee"
            cle["custom_nom"] = ""

    # 🚫 Si Libre → fini
    if not fid:
        save_formateurs(formateurs)
        return {"ok": True}

    # ✅ Sinon attribuer la clé
    formateur = next((f for f in formateurs if f["id"] == fid), None)
    if not formateur:
        return {"ok": False, "error": "Formateur introuvable"}

    formateur["cle"]["attribuee"] = True
    formateur["cle"]["numero"] = numero
    formateur["cle"]["statut"] = "attribuee"
    formateur["cle"]["custom_nom"] = ""

    save_formateurs(formateurs)
    return {"ok": True}


@app.route("/badge/assign", methods=["POST"])
def assign_badge():
    payload = request.get_json()
    numero = str(payload.get("numero"))
    fid = payload.get("fid")

    formateurs = load_formateurs()

    # 🔄 Retirer ce badge à tous les formateurs
    for f in formateurs:
        badge = f.setdefault("badge", {})
        if badge.get("numero") == numero:
            badge["attribue"] = False
            badge["numero"] = ""
            badge["statut"] = "non_attribue"

    # 🚫 Si Libre
    if not fid:
        save_formateurs(formateurs)
        return {"ok": True}

    # ✅ Sinon attribuer le badge
    formateur = next((f for f in formateurs if f["id"] == fid), None)
    if not formateur:
        return {"ok": False, "error": "Formateur introuvable"}

    formateur["badge"]["attribue"] = True
    formateur["badge"]["numero"] = numero
    formateur["badge"]["statut"] = "attribue"

    save_formateurs(formateurs)
    return {"ok": True}

# ------------------------------------------------------------
# 🟩 GESTION DU DISTRIBUTEUR — PERSISTENCE JSON
# ------------------------------------------------------------

DISTRIBUTEUR_FILE = os.path.join(DATA_DIR, "distributeur.json")

def load_distributeur():
    """Charge le distributeur depuis le fichier JSON, ou crée une structure par défaut."""
    default_data = {
        "lignes": [
            {"id": 1, "produits": []},
            {"id": 2, "produits": []},
            {"id": 3, "produits": []},
            {"id": 4, "produits": []},
            {"id": 5, "produits": []}
        ]
    }

    if os.path.exists(DISTRIBUTEUR_FILE):
        try:
            with open(DISTRIBUTEUR_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("lignes"), list):
                    return data
        except Exception:
            app.logger.exception("Impossible de lire %s", DISTRIBUTEUR_FILE)

            # Tentative de récupération: certains fichiers ont du texte parasite
            # autour d'un JSON valide (copier/coller, merge, etc.).
            try:
                with open(DISTRIBUTEUR_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    recovered = json.loads(content[start:end + 1])
                    if isinstance(recovered, dict) and isinstance(recovered.get("lignes"), list):
                        app.logger.warning("Récupération partielle de %s après corruption JSON", DISTRIBUTEUR_FILE)
                        return recovered
            except Exception:
                app.logger.exception("Récupération impossible pour %s", DISTRIBUTEUR_FILE)

    return default_data

def save_distributeur(data):
    """Sauvegarde complète du distributeur."""
    with open(DISTRIBUTEUR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



@app.route("/distributeur")
def distributeur_home():
    data = load_distributeur()
    return render_template("distributeur.html", data=data)

@app.route("/distributeur/add/<int:ligne_id>", methods=["POST"])
def distributeur_add(ligne_id):
    data = load_distributeur()

    # Trouver la ligne
    ligne = next((l for l in data["lignes"] if l["id"] == ligne_id), None)
    if not ligne:
        abort(404)

    # Ajouter un produit vide
    new_product = {
        "id": str(uuid.uuid4())[:8],
        "nom": "",
        "qte_cible": 0,
        "qte_actuelle": 0,
        "prix_achat": 0.0,
        "prix_vente": 0.0
    }

    ligne["produits"].append(new_product)
    save_distributeur(data)

    return redirect(url_for("distributeur_home"))

def to_int(x):
    try:
        return int(x)
    except:
        return 0

def to_float(x):
    try:
        return float(x)
    except:
        return 0.0


@app.route("/distributeur/update/<int:ligne_id>/<pid>", methods=["POST"])
def distributeur_update(ligne_id, pid):
    data = load_distributeur()

    for ligne in data["lignes"]:
        if ligne["id"] == ligne_id:
            for produit in ligne["produits"]:
                if produit["id"] == pid:

                    produit["nom"] = request.form.get("nom", "")

                    produit["qte_cible"] = to_int(request.form.get("qte_cible"))
                    produit["qte_actuelle"] = to_int(request.form.get("qte_actuelle"))

                    produit["prix_achat"] = to_float(request.form.get("prix_achat"))
                    produit["prix_vente"] = to_float(request.form.get("prix_vente"))

                    save_distributeur(data)
                    return "ok"

    return "error", 400



@app.route("/distributeur/delete/<int:ligne_id>/<pid>", methods=["POST"])
def distributeur_delete(ligne_id, pid):
    data = load_distributeur()

    # retrouver la ligne
    ligne = next((l for l in data["lignes"] if l["id"] == ligne_id), None)
    if not ligne:
        abort(404)

    # filtrer les produits en supprimant celui voulu
    ligne["produits"] = [p for p in ligne["produits"] if p.get("id") != pid]

    save_distributeur(data)

    return redirect(url_for("distributeur_home"))

@app.route("/reassort")
def distributeur_reassort():
    data = load_distributeur()

    items = []
    for ligne in data["lignes"]:
        for p in ligne["produits"]:
            q_cible = p.get("qte_cible", 0)
            q_actuelle = p.get("qte_actuelle", 0)

            if q_actuelle < q_cible:
                items.append({
                    "ligne_id": ligne["id"],
                    "produit_id": p["id"],
                    "nom": p.get("nom", "Produit"),
                    "reassort": q_cible - q_actuelle,
                    "q_cible": q_cible,
                    "q_actuelle": q_actuelle,
                })

    # Priorité visuelle: afficher d'abord les étages 4 puis 5 dans la liste de réassort.
    etage_priority = {4: 0, 5: 1}
    items.sort(key=lambda item: (etage_priority.get(item["ligne_id"], 2), item["ligne_id"], item["nom"].lower()))

    return render_template("reassort.html", items=items)


@app.route("/distributeur/approvisionnement")
def distributeur_approvisionnement():
    data = load_distributeur()

    produits = []
    for ligne in data["lignes"]:
        for p in ligne["produits"]:
            nom = (p.get("nom") or "").strip()
            if not nom:
                continue
            produits.append({
                "id": p["id"],
                "ligne_id": ligne["id"],
                "nom": nom,
            })

    produits.sort(key=lambda item: (item["ligne_id"], item["nom"].lower()))

    return render_template("approvisionnement.html", produits=produits)

@app.route("/reassort/valider/<int:ligne_id>/<produit_id>", methods=["POST"])
def distributeur_reassort_valider(ligne_id, produit_id):
    data = load_distributeur()

    for ligne in data["lignes"]:
        if ligne["id"] == ligne_id:
            for p in ligne["produits"]:
                if str(p["id"]) == str(produit_id):
                    # Mise à jour automatique
                    p["qte_actuelle"] = p.get("qte_cible", 0)

                    save_distributeur(data)
                    break

    return redirect(url_for("distributeur_reassort"))

start_price_adaptator_scheduler()

import xml.etree.ElementTree as ET
from flask import Response, request
from datetime import datetime

def _first_text(elem, tag_name):
    if elem is None:
        return None
    for child in list(elem):
        if child.tag.endswith(tag_name):
            return (child.text or "").strip()
    return None

@app.post("/webhooks/salesforce/lead-outbound")
def salesforce_lead_outbound():
    # sécurité optionnelle
    secret_expected = os.environ.get("SF_OUTBOUND_SECRET")
    if secret_expected and request.args.get("key") != secret_expected:
        return Response("Unauthorized", status=401)

    raw = request.data.decode("utf-8", errors="ignore")
    if not raw.strip():
        return Response("Empty body", status=400)

    try:
        root = ET.fromstring(raw)
    except Exception as e:
        return Response(f"Bad XML: {e}", status=400)

    # On récupère TON format de stockage (dict)
    data = load_price_adaptator_data()

    now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    added = 0

    for notif in root.iter():
        if not notif.tag.endswith("notifications"):
            continue

        sobject = None
        for e in notif.iter():
            if e.tag.endswith("sObject"):
                sobject = e
                break
        if sobject is None:
            continue

        # mapping Outbound -> ton modèle prospect
        prospect = {
            "id": str(uuid.uuid4()),
            "nom": normalize_price_adaptator_nom(_first_text(sobject, "LastName")),
            "prenom": normalize_price_adaptator_prenom(_first_text(sobject, "FirstName")),
            "cpf": float(_first_text(sobject, "Montant_CPF__c") or 0),
            "email": (_first_text(sobject, "Email") or "").strip(),
            "telephone": (_first_text(sobject, "Phone") or "").strip(),
            "formation": normalize_price_adaptator_formation(_first_text(sobject, "Type_de_formation__c")),
            "sent": False,
            "sentAt": None,
            "proposed_price": None,
            "last_error": None,
            "last_attempt_at": None,
            "created_at": datetime.now().isoformat(),
            "salesforce": {
                "lead_id": _first_text(sobject, "Id"),
                "received_at": now_iso
            }
        }

        # on n’ajoute que si formation ok + nom/prénom ok
        if prospect["nom"] and prospect["prenom"] and prospect["formation"]:
            data["prospects"].insert(0, prospect)
            added += 1

    save_price_adaptator_data(data)

    soap_response = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Body>
    <notificationsResponse xmlns="http://soap.sforce.com/2005/09/outbound">
      <Ack>true</Ack>
    </notificationsResponse>
  </soapenv:Body>
</soapenv:Envelope>
"""
    return Response(soap_response, status=200, content_type="text/xml; charset=utf-8")










    
