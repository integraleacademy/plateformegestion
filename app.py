import os, json, uuid, base64
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, abort, flash
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")

# --- Filtre date FR ---
def format_date(value):
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
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

# -----------------------
# Modèles d'étapes
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

    # AVANT EXAM
    {"name":"Impression des dossiers d’examen", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Saisie des SST", "relative_to":"exam", "offset_type":"before", "days":7},
    {"name":"Impression des SST", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Impression évaluation de fin de formation", "relative_to":"exam","offset_type":"before","days":5},

    # JOUR DE L’EXAMEN (NOUVEAU)
    {"name":"Session examen clôturée", "relative_to":"exam", "offset_type":"after", "days":0},
    {"name":"Frais ADEF réglés", "relative_to":"exam", "offset_type":"after", "days":0},
    {"name":"Documents examen envoyés à l’ADEF", "relative_to":"exam", "offset_type":"after", "days":0},

    # APRES EXAM
    {"name":"Envoyer mail stagiaires attestations de formation","relative_to":"exam","offset_type":"after","days":2},
    {"name":"Message avis Google","relative_to":"exam","offset_type":"after","days":2},

    # APRES EXAM (NOUVEAU)
    {"name":"Diplômes reçus", "relative_to":"exam", "offset_type":"after", "days":7},
    {"name":"Diplômes envoyés aux stagiaires", "relative_to":"exam", "offset_type":"after", "days":10},
]

SSIAP_STEPS = [
    {"name": "Nomination jury examen", "relative_to": "exam", "offset_type": "before", "days": 65},
    {"name": "Prévenir centre d’examen", "relative_to": "exam", "offset_type": "before", "days": 65},
    {"name": "Envoi convention au SDIS", "relative_to": "exam", "offset_type": "before", "days": 65},
    {"name": "Planification YPAREO", "relative_to": "start", "offset_type": "before", "days": 10},
    {"name": "Contrat envoyé au formateur", "relative_to": "start", "offset_type": "before", "days": 5},
    {"name": "Contrat formateur imprimé", "relative_to": "start", "offset_type": "before", "days": 5},
    {"name": "Impression des dossiers d’examen", "relative_to": "exam", "offset_type": "before", "days": 5},
    {"name": "Impression évaluation de fin de formation", "relative_to": "exam", "offset_type": "before", "days": 5},
    {"name": "Envoyer mail stagiaires attestations de formation", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "Message avis Google", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "Diplômes envoyés au SDIS", "relative_to": "exam", "offset_type": "after", "days": 2},
    {"name": "Diplômes reçus", "relative_to": "exam", "offset_type": "after", "days": 30},
    {"name": "Diplômes envoyés aux stagiaires", "relative_to": "exam", "offset_type": "after", "days": 30},
]

FORMATION_COLORS = {
    "APS": "#1b9aaa",
    "A3P": "#2a9134",
    "SSIAP": "#c0392b",
    "DIRIGEANT": "#8e44ad",
}

def default_steps_for(formation):
    if formation in ("APS", "A3P"):
        steps = APS_A3P_STEPS
    elif formation == "SSIAP":
        steps = SSIAP_STEPS
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
    return None

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None

def deadline_for(step_index, session):
    rule = _rule_for(session["formation"], step_index)
    if not rule:
        return None

    base_date = None
    if rule["relative_to"] == "exam":
        base_date = parse_date(session.get("date_exam"))
    elif rule["relative_to"] == "start":
        base_date = parse_date(session.get("date_debut"))

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
    return ("late" if now.date() > dl.date() else "on_time", dl)

def snapshot_overdue(session):
    """Retourne les étapes en retard avec leur deadline (triées par urgency)."""
    overdue = []
    for i, step in enumerate(session["steps"]):
        st, dl = status_for_step(i, session)
        if st == "late":
            overdue.append((step["name"], dl))
    overdue.sort(key=lambda x: (x[1] or datetime.max))
    return overdue

# -----------------------
# Mail quotidien global
# -----------------------
def _late_phrase(dl: datetime) -> str:
    """Retourne 'Retard de N jours (JJ-MM-AAAA)' pour le mail."""
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
    <body style="font-family:Arial,Helvetica,sans-serif;background:#f7f7f7;padding:30px;margin:0;">
      <div style="max-width:720px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.1)">
        <div style="background:#121212;color:#fff;padding:24px 20px;text-align:center;">
          {('<img src="data:image/png;base64,'+logo_base64+'" alt="Intégrale Academy" style="height:90px;margin-bottom:10px;border-radius:12px;">') if logo_base64 else ''}
          <h1 style="margin:10px 0;font-size:24px;">⚠️ Récapitulatif des retards — Intégrale Academy</h1>
          <div style="font-size:14px;opacity:.9;">{now_txt}</div>
        </div>
        <div style="padding:24px;">
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
              <div style="background:{color};color:#fff;font-weight:700;border-radius:30px;padding:6px 14px;font-size:14px;letter-spacing:.5px;">
                {s["formation"]}
              </div>
              <div style="font-size:14px;color:#444;">
                <b>Début :</b> {format_date(s.get("date_debut","—"))} &nbsp;&nbsp;
                <b>Fin :</b> {format_date(s.get("date_fin","—"))} &nbsp;&nbsp;
                <b>Examen :</b> {format_date(s.get("date_exam","—"))}
              </div>
            </div>
            <ul style="margin:12px 0 0 18px;padding:0;color:#333;font-size:15px;line-height:1.6;">
        """
        for name, dl in overdue:
            html += f"<li style='margin-bottom:4px;'>• {name} — {_late_phrase(dl)}</li>"
        html += """
            </ul>
          </div>
        """

    if not found_any:
        html += """
          <p style="text-align:center;font-size:15px;color:#444;margin:20px 0;">
            ✅ Aucun retard à signaler aujourd’hui.
          </p>
        """

    html += """
        </div>
        <div style="background:#fafafa;text-align:center;padding:14px;font-size:13px;color:#666;">
          Vous recevez ce mail automatiquement chaque matin à 8h.
        </div>
      </div>
    </body>
    """
    return html

def send_daily_overdue_summary():
    """Envoie un seul mail par jour à 8h avec tous les retards."""
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

# -----------------------
# Routes principales
# -----------------------
@app.route("/")
def index():
    return render_template("index.html", title="Plateforme de gestion Intégrale Academy")

@app.route("/sessions")
def sessions_home():
    data = load_sessions()
    active = [s for s in data["sessions"] if not s.get("archived")]
    archived = [s for s in data["sessions"] if s.get("archived")]
    for s in data["sessions"]:
        s["color"] = FORMATION_COLORS.get(s["formation"], "#555")
    return render_template("sessions.html", title="Gestion des sessions",
                           active_sessions=active, archived_sessions=archived)

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
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)

    statuses = []
    for i in range(len(session["steps"])):
        st, dl = status_for_step(i, session)
        statuses.append({
            "status": st,
            "deadline": (dl.strftime("%Y-%m-%d") if dl else None)
        })

    auto_archive_if_all_done(session)
    save_sessions(data)
    return render_template("session_detail.html",
                           title=f"{session['formation']} — Détail",
                           s=session, statuses=statuses)

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

# --- Cron léger (archivage auto) ---
@app.route("/cron-check")
def cron_check():
    data = load_sessions()
    for session in data["sessions"]:
        auto_archive_if_all_done(session)
    save_sessions(data)
    return "Cron check terminé", 200

# --- Cron quotidien 8h (mail global) ---
@app.route("/cron-daily-summary")
def cron_daily_summary():
    send_daily_overdue_summary()
    return "Mail récapitulatif envoyé", 200
