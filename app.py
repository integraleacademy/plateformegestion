
import os
from flask import Flask, render_template, send_from_directory

app = Flask(__name__)

# Répertoire de données persistant (Render monte un disque sur /mnt/data)
DATA_DIR = os.environ.get("DATA_DIR", "/mnt/data")
os.makedirs(DATA_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html", title="Plateforme de gestion Intégrale Academy")

@app.route("/sessions")
def sessions():
    # Page à paramétrer ensemble par la suite
    return render_template("sessions.html", title="Gestion des sessions")

# Santé simple
@app.route("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
