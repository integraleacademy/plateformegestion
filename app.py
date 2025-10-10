import os, json, uuid, hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, abort, flash

# --- Email ---
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")

# --- Filtre date FR ---
def format_date(value):
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except:
        return value

app.jinja_env.filters['datefr'] = format_date

# --- Persistance ---
DATA_DIR = os.environ.get("DATA_DIR", "/mnt/data")
os.makedirs(DATA_DIR, exist_ok=True)
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")

FROM_EMAIL = os.environ.get("FROM_EMAIL")           # ecole@integraleacademy.com
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")   # mot de passe application
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

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

# -----------------------
# Modèle étapes
# -----------------------
APS_A3P_STEPS = [
    {"name":"Création session ADEF", "relative_to":"start", "offset_type":"before", "days":15},
    {"name":"Création session CNAPS", "relative_to":"start", "offset_type":"before", "days":20},
    {"name":"Nomination jury examen", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Planification YPAREO", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Contrat envoyé au formateur", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Contrat formateur imprimé", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Saisie des candidats ADEF", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Impression des fiches CNIL", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Validation session ADEF", "relative_to":"start", "offset_type":"before", "days":2},
    {"name":"Fabrication badge formateur", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Vérification dossier formateur", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Envoyer test de français", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Corriger et imprimer test de français", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Envoyer lien à compléter stagiaires", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Signature des fiches CNIL", "relative_to":"start", "offset_type":"after", "days":1},
    {"name":"Impression des dossiers d’examen", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Saisie des SST", "relative_to":"exam", "offset_type":"before", "days":7},
    {"name":"Impression des SST", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Impression évaluation de fin de formation", "relative_to":"exam","offset_type":"before","days":5},
    {"name":"Envoyer mail stagiaires attestations de formation","relative_to":"exam","offset_type":"after","days":2},
    {"name":"Message avis Google","relative_to":"exam","offset_type":"after","days":2},
]

FORMATION_COLORS = {
    "APS": "#1b9aaa",
    "A3P": "#2a9134",
    "SSIAP": "#c0392b",
    "DIRIGEANT": "#8e44ad",
}

def default_steps_for(formation):
    if formation in ("APS", "A3P"):
        return [{"name": s["name"], "done": False, "done_at": None} for s in APS_A3P_STEPS]
    return []

# -----------------------
# Statuts
# -----------------------
def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None

def deadline_for(step_index, session):
    if session["formation"] not in ("APS", "A3P"):
        return None
    rule = APS_A3P_STEPS[step_index]
    base_date = None
    if rule["relative_to"] == "exam":
        base_date = parse_date(session.get("date_exam"))
    elif rule["relative_to"] == "start":
        base_date = parse_date(session.get("date_debut"))
    if not base_date:
        return None
    return base_date - timedelta(days=rule["days"]) if rule["offset_type"] == "before" else base_date + timedelta(days=rule["days"])

def status_for_step(step_index, session, now=None):
    if now is None:
        now = datetime.now()
    dl = deadline_for(step_index, session)
    if dl is None:
        return ("n/a", None)
    step = session["steps"][step_index]
    if step["done"]:
        return ("done", dl)
    return ("late" if now > dl else "on_time", dl)

def snapshot_overdue(session):
    return [step["name"] for i, step in enumerate(session["steps"]) if status_for_step(i, session)[0] == "late"]

def auto_archive_if_all_done(session):
    if not session.get("archived") and session["steps"] and all(s["done"] for s in session["steps"]):
        session["archived"] = True
        session["archived_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# -----------------------
# Envoi mail global
# -----------------------
def send_global_overdue_report(data):
    if not FROM_EMAIL or not EMAIL_PASSWORD:
        return

    sessions = data["sessions"]
    report_lines = []

    for session in sessions:
        overdue = snapshot_overdue(session)
        if overdue:
            report_lines.append(
                f"📚 {session['formation']} "
                f"(Début : {session.get('date_debut','N/A')} | "
                f"Fin : {session.get('date_fin','N/A')} | "
                f"Examen : {session.get('date_exam','N/A')})\n"
                + "\n".join([f"   • {step}" for step in overdue])
                + "\n"
            )

    if not report_lines:
        body = "✅ Aucun retard détecté aujourd’hui pour les sessions."
    else:
        body = "⚠️ Voici la liste des étapes en retard :\n\n" + "\n".join(report_lines)

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = "📌 Récapitulatif des retards — Intégrale Academy"
    msg["From"] = FROM_EMAIL
    msg["To"] = "clement@integraleacademy.com"

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(FROM_EMAIL, EMAIL_PASSWORD)
            server.sendmail(FROM_EMAIL, ["clement@integraleacademy.com"], msg.as_string())
        print("✅ Mail global envoyé")
    except Exception as e:
        print("Erreur envoi mail global:", e)

# -----------------------
# Routes
# -----------------------
@app.route("/")
def index():
    return render_template("index.html", title="Plateforme de gestion Intégrale Academy")

@app.route("/sessions", methods=["GET"])
def sessions_home():
    data = load_sessions()
    active = [s for s in data["sessions"] if not s.get("archived")]
    archived = [s for s in data["sessions"] if s.get("archived")]
    for s in data["sessions"]:
        s["color"] = FORMATION_COLORS.get(s["formation"], "#555")
    return render_template("sessions.html", title="Gestion des sessions", active_sessions=active, archived_sessions=archived)

@app.route("/sessions/create", methods=["POST"])
def create_session():
    formation = request.form.get("formation", "").strip().upper()
    date_debut = request.form.get("date_debut", "").strip()
    date_fin = request.form.get("date_fin", "").strip()
    date_exam = request.form.get("date_exam", "").strip()
    if formation not in ("APS", "A3P", "SSIAP", "DIRIGEANT"):
        flash("Formation invalide.", "error")
        return redirect(url_for("sessions_home"))
    sid = str(uuid.uuid4())[:8]
    session = {
        "id": sid,
        "formation": formation,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "date_exam": date_exam,
        "color": FORMATION_COLORS.get(formation, "#555"),
        "steps": default_steps_for(formation),
        "archived": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    data = load_sessions()
    data["sessions"].append(session)
    save_sessions(data)
    return redirect(url_for("session_detail", sid=sid))

@app.route("/sessions/<sid>", methods=["GET"])
def session_detail(sid):
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)
    statuses = [{"status": status_for_step(i, session)[0], "deadline": (status_for_step(i, session)[1].strftime("%Y-%m-%d") if status_for_step(i, session)[1] else None)} for i in range(len(session["steps"]))]
    auto_archive_if_all_done(session)
    save_sessions(data)
    return render_template("session_detail.html", title=f"{session['formation']} — Détail", s=session, statuses=statuses)

@app.route("/sessions/<sid>/edit", methods=["GET", "POST"])
def edit_session(sid):
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)
    if request.method == "POST":
        session["date_debut"] = request.form.get("date_debut", "").strip()
        session["date_fin"] = request.form.get("date_fin", "").strip()
        session["date_exam"] = request.form.get("date_exam", "").strip()
        save_sessions(data)
        flash("Session mise à jour.", "ok")
        return redirect(url_for("session_detail", sid=sid))
    return render_template("session_edit.html", s=session)

@app.route("/sessions/<sid>/toggle_step", methods=["POST"])
def toggle_step(sid):
    idx = int(request.form.get("index", "-1"))
    data = load_sessions()
    session = find_session(data, sid)
    if not session or idx < 0 or idx >= len(session["steps"]):
        abort(400)
    step = session["steps"][idx]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    step["done"] = not step["done"]
    step["done_at"] = now if step["done"] else None
    auto_archive_if_all_done(session)
    save_sessions(data)
    return redirect(url_for("session_detail", sid=sid) + f"#step{idx}")

@app.route("/sessions/<sid>/delete", methods=["POST"])
def delete_session(sid):
    data = load_sessions()
    data["sessions"] = [s for s in data["sessions"] if s["id"] != sid]
    save_sessions(data)
    flash("Session supprimée.", "ok")
    return redirect(url_for("sessions_home"))

@app.route("/healthz")
def healthz():
    return "ok"

# --- Cron ---
@app.route("/cron-check")
def cron_check():
    data = load_sessions()
    for session in data["sessions"]:
        auto_archive_if_all_done(session)
    save_sessions(data)

    send_global_overdue_report(data)
    return "Cron check terminé (rapport global envoyé)", 200
