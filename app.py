import os, json, uuid, base64
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, abort, flash
import smtplib
from email.mime.text import MIMEText

# --- 🔧 Forcer le fuseau horaire français ---
os.environ['TZ'] = 'Europe/Paris'
import time
time.tzset()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")


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
]

SSIAP_STEPS = [
    {"name":"Nomination jury examen", "relative_to":"exam", "offset_type":"before", "days":65},
    {"name":"Prévenir centre d’examen", "relative_to":"exam", "offset_type":"before", "days":65},
    {"name":"Envoi convention au SDIS", "relative_to":"exam", "offset_type":"before", "days":65},
    {"name":"Planification YPAREO", "relative_to":"start", "offset_type":"before", "days":10},
    {"name":"Contrat envoyé au formateur", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Contrat formateur imprimé", "relative_to":"start", "offset_type":"before", "days":5},
    {"name":"Impression des dossiers d’examen", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Impression évaluation de fin de formation", "relative_to":"exam", "offset_type":"before", "days":5},
    {"name":"Envoyer mail stagiaires attestations de formation", "relative_to":"exam", "offset_type":"after", "days":2},
    {"name":"Message avis Google", "relative_to":"exam", "offset_type":"after", "days":2},
    {"name":"Diplômes envoyés au SDIS", "relative_to":"exam", "offset_type":"after", "days":2},
    {"name":"Diplômes reçus", "relative_to":"exam", "offset_type":"after", "days":30},
    {"name":"Diplômes envoyés aux stagiaires", "relative_to":"exam", "offset_type":"after", "days":30},
    
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

# -----------------------
# Routes principales
# -----------------------
@app.route("/")
def index():
    return render_template("index.html", title="Plateforme de gestion Intégrale Academy")

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
    data = load_sessions()
    session = find_session(data, sid)
    if not session:
        abort(404)

    # 🔄 Synchronise cette session avant de l’afficher
    sync_steps(session)
    save_sessions(data)


    statuses = []
    for i in range(len(session["steps"])):
        st, dl = status_for_step(i, session)
        statuses.append({"status": st, "deadline": (dl.strftime("%Y-%m-%d") if dl else None)})
    order = sorted(range(len(session["steps"])), key=lambda i: deadline_for(i, session) or datetime.max)
    auto_archive_if_all_done(session)
    save_sessions(data)
    return render_template("session_detail.html", title=f"{session['formation']} — Détail", s=session, statuses=statuses, order=order, now=datetime.now)

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
