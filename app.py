import os, json, uuid, base64
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, abort, flash
import smtplib
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for, abort, flash, send_from_directory
from werkzeug.utils import secure_filename
from functools import wraps
from flask import session



# --- 🔧 Forcer le fuseau horaire français ---
os.environ['TZ'] = 'Europe/Paris'
import time
time.tzset()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")

ADMIN_USER = os.environ.get("ADMIN_USER")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

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

    # ✅ autoriser lien public formateur (upload avec token)
    if path.startswith("/formateurs/") and "/upload" in path:
        return None

    # ✅ autoriser accès préfecture (auth basic gérée dans la route)
    if path.startswith("/prefecture/"):
        return None

    # ✅ autoriser les routes cron (Render Cron)
    if path.startswith("/cron-"):
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

FROM_EMAIL = os.environ.get("FROM_EMAIL")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

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
                    return data
        except Exception:
            pass
    return {"sessions": []}

def save_sessions(data):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def find_session(data, sid):
    for s in data["sessions"]:
        if s["id"] == sid:
            return s
    return None

def sync_steps(session):
    """Ajoute automatiquement les nouvelles étapes manquantes selon la formation."""
    formation = session.get("formation")
    if formation not in ("APS", "A3P", "SSIAP"):
        return

    # Récupère la liste actuelle des règles depuis le code
    rules = APS_A3P_STEPS if formation in ("APS", "A3P") else SSIAP_STEPS
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
    {"name":"Impression des dossiers d’examen", "relative_to":"exam", "offset_type":"before", "days":5},
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

def default_steps_for(formation):
    if formation in ("APS", "A3P"):
        steps = APS_A3P_STEPS
    elif formation == "SSIAP":
        steps = SSIAP_STEPS
    elif formation == "GENERAL":        # ✅ ajoute ceci
        steps = GENERAL_STEPS
    else:
        steps = []
    return [{"name": s["name"], "done": False, "done_at": None} for s in steps]


# -----------------------
# Statuts / échéances
# -----------------------
def _rule_for(formation, step_index):
    if formation in ("APS", "A3P"):
        return APS_A3P_STEPS[step_index]
    if formation == "SSIAP":
        return SSIAP_STEPS[step_index]
    if formation == "GENERAL":
        return GENERAL_STEPS[step_index]
    return None


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

def send_daily_overdue_summary():
    if not FROM_EMAIL or not EMAIL_PASSWORD:
        print("⚠️ EMAIL non configuré")
        return
    data = load_sessions()
    sessions = data["sessions"]
    html = generate_daily_overdue_email(sessions)
    msg = MIMEText(html, "html", _charset="utf-8")
    msg["Subject"] = "⚠️ Récapitulatif des retards — Intégrale Academy"
    msg["From"] = FROM_EMAIL
    msg["To"] = "clement@integraleacademy.com"
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(FROM_EMAIL, EMAIL_PASSWORD)
            server.sendmail(FROM_EMAIL, ["clement@integraleacademy.com"], msg.as_string())
        print("✅ Mail quotidien envoyé avec succès")
    except Exception as e:
        print("❌ Erreur envoi mail quotidien :", e)

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
            if doc.get("status") == "non_conforme":
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
        formateurs_non_conformes=nb_non_conformes
    )


@app.route("/sessions")
def sessions_home():
    data = load_sessions()
    # 🔄 Synchronise automatiquement les étapes manquantes pour chaque session
    for s in data["sessions"]:
        sync_steps(s)
    save_sessions(data)

    active = [s for s in data["sessions"] if not s.get("archived")]
    archived = [s for s in data["sessions"] if s.get("archived")]
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
    today = datetime.now().date()
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
        statuses=statuses,
        order=order,
        now=datetime.now
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


@app.route("/sessions/<sid>/delete", methods=["POST"])
def delete_session(sid):
    data = load_sessions()
    data["sessions"] = [s for s in data["sessions"] if s["id"]!=sid]
    save_sessions(data)
    flash("Session supprimée.","ok")
    return redirect(url_for("sessions_home"))

@app.route("/healthz")
def healthz():
    return "ok"

@app.route("/cron-check")
def cron_check():
    data = load_sessions()
    for session in data["sessions"]:
        auto_archive_if_all_done(session)
    save_sessions(data)
    return "Cron check terminé", 200

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
    if os.path.exists(FORMATEURS_FILE):
        try:
            with open(FORMATEURS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_formateurs(data):
    with open(FORMATEURS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
    6: "Formateurs",
    7: "Formateurs",
    8: "Formateurs",
    9: "Formateurs",
    10: "Formateurs",
    11: "Formateurs",
    12: "Formateurs",
    13: "Formateurs",
    14: "Formateurs",
    15: "Formateurs"
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

        # ✅ calcul conformité
        total = 0
        conformes = 0

        for doc in f.get("documents", []):
            auto_update_document_status(doc)

            status = doc.get("status", "non_conforme")
            if status != "non_concerne":
                total += 1
                if status == "conforme":
                    conformes += 1

        f["conformite"] = {"conformes": conformes, "total": total}

    save_formateurs(formateurs)

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
    total_cles = list(range(1, 16))       # Clés 1 → 15
    total_badges = list(range(1, 16))     # Badges 1 → 15

    # ===== NUMÉROS DISPONIBLES =====
    cles_dispos = [n for n in total_cles if n not in liste_cles]
    badges_dispos = [n for n in total_badges if n not in liste_badges]

    # ===== ÉTAT COMPLET CLÉS & BADGES =====
    etat_cles, etat_badges = get_etat_cles_badges(formateurs, 15, 15)


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
    etat_cles, etat_badges = get_etat_cles_badges(formateurs, 15, 15)

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
        if st in ("non_concerne", "conforme", "non_conforme"):
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
        liste_formateurs = set()   # éviter les doublons

        for f in formateurs:
            nom_complet = f"{f.get('prenom','')} {f.get('nom','')}".strip()
            for doc in f.get("documents", []):
                auto_update_document_status(doc)
                if doc.get("status") == "non_conforme":
                    total_non_conformes += 1
                    liste_formateurs.add(nom_complet)

        payload = {
            "non_conformes": total_non_conformes,
            "liste": sorted(list(liste_formateurs))
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
        doc["status"] = "conforme"
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

@app.route("/distributeur/update/<int:ligne_id>/<pid>", methods=["POST"])
def distributeur_update(ligne_id, pid):
    data = load_distributeur()

    # retrouver la ligne
    ligne = next((l for l in data["lignes"] if l["id"] == ligne_id), None)
    if not ligne:
        abort(404)

    # retrouver le produit
    produit = next((p for p in ligne["produits"] if p["id"] == pid), None)
    if not produit:
        abort(404)

    # mise à jour
    produit["nom"] = request.form.get("nom", "").strip()
    produit["qte_cible"] = int(request.form.get("qte_cible", 0))
    produit["qte_actuelle"] = int(request.form.get("qte_actuelle", 0))
    produit["prix_achat"] = float(request.form.get("prix_achat", 0))
    produit["prix_vente"] = float(request.form.get("prix_vente", 0))

    save_distributeur(data)

    return redirect(url_for("distributeur_home"))

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








    






