import json
import os
import uuid

FORMATIONS = ["A3P", "APS", "SSIAP", "DIRIGEANT", "VTC"]
TEMPLATES = [
    {"id": "hero_editorial", "name": "Hero éditorial"},
    {"id": "comparison", "name": "Comparatif 2 colonnes"},
    {"id": "key_figures", "name": "Chiffres clés"},
    {"id": "timeline", "name": "Timeline / étapes"},
    {"id": "faq", "name": "FAQ / idées reçues"},
    {"id": "dashboard", "name": "Dashboard / indicateurs"},
    {"id": "alert_card", "name": "Carte alerte"},
    {"id": "program", "name": "Programme"},
]

VISUAL_THEMES = {
    "A3P": {"name":"A3P","tone":"premium","primary":"#A38B2E","secondary":"#D4C56A","accent":"#E8DFA8","bgLight":"#F6F3E7","bgDark":"#1F1E17","textMain":"#1C1C18","textMuted":"#6C695D","highlightStyle":"rounded-olive","iconStyle":"premium-security","badge":"PROTECTION PREMIUM"},
    "APS": {"name":"APS","tone":"pro / pédagogique","primary":"#0F4C81","secondary":"#3A84C6","accent":"#A9D3F5","bgLight":"#F4F8FC","bgDark":"#10273D","textMain":"#14202B","textMuted":"#58708A","highlightStyle":"rounded-blue","iconStyle":"training-security","badge":"SÉCURITÉ PRIVÉE"},
    "SSIAP": {"name":"SSIAP","tone":"alerte / technique","primary":"#C0392B","secondary":"#E86B5A","accent":"#F6C1B8","bgLight":"#FCF4F2","bgDark":"#2E1715","textMain":"#221615","textMuted":"#7E5A56","highlightStyle":"rounded-red","iconStyle":"fire-safety","badge":"SÉCURITÉ INCENDIE"},
    "DIRIGEANT": {"name":"DIRIGEANT","tone":"executive / réglementaire","primary":"#5D3E8E","secondary":"#8A67C2","accent":"#D8C8F1","bgLight":"#F7F3FC","bgDark":"#22182F","textMain":"#231B2D","textMuted":"#6D5C7D","highlightStyle":"rounded-purple","iconStyle":"executive-compliance","badge":"PILOTAGE & CONFORMITÉ"},
    "VTC": {"name":"VTC","tone":"mobilité / service","primary":"#0E7C66","secondary":"#37B39B","accent":"#BFE7DE","bgLight":"#F2FBF8","bgDark":"#16332D","textMain":"#17302B","textMuted":"#5D7B74","highlightStyle":"rounded-green","iconStyle":"premium-mobility","badge":"MOBILITÉ PREMIUM"},
}

DEFAULT_SLIDE = {
    "template":"hero_editorial","formation":"A3P","category_label":"FORMATION PROFESSIONNELLE","eyebrow":"A3P • SESSION 2026",
    "title":"Devenez agent de protection physique des personnes.","highlight_text":"protection physique",
    "intro":"Une formation complète pour accéder aux métiers de la protection rapprochée.",
    "text":"Un visuel premium, lisible et prêt pour vos réseaux sociaux.",
    "key_points":["Session à Puget-sur-Argens","Formation professionnalisante","Places limitées"],
    "stats":[{"label":"Durée","value":"175 h"},{"label":"Lieu","value":"Puget-sur-Argens"},{"label":"Financement","value":"CPF"}],
    "badges":["Qualiopi","CPF","Présentiel"],"cta":"Contactez-nous pour vous inscrire","slide_number":1,"slide_total":1,
    "center_name":"Intégrale Academy","phone":"","website":"","location":"Puget-sur-Argens","date":"","duration":"175 h","price":"","financing":"CPF / autres"
}


def social_visuals_file(data_dir):
    return os.path.join(data_dir, "social_visuals.json")


def load_social_visuals(data_dir):
    path = social_visuals_file(data_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("posts", [])
                    return data
        except Exception:
            pass
    return {"posts": []}


def save_social_visuals(data_dir, data):
    path = social_visuals_file(data_dir)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def normalize_formation(value):
    raw = (value or "").upper()
    if raw in {"DESP", "DIRIGEANT", "DIRIGEANT D'ENTREPRISE"}:
        return "DIRIGEANT"
    if "SSIAP" in raw:
        return "SSIAP"
    if raw in FORMATIONS:
        return raw
    return "APS"


def generate_content_from_topic(topic):
    topic = (topic or "").strip()
    upper = topic.upper()
    formation = next((f for f in FORMATIONS if f in upper), "APS")
    if "DESP" in upper:
        formation = "DIRIGEANT"
    template = "timeline" if any(w in upper for w in ["ÉTAPE", "ETAPE", "INSCRIPTION"]) else "program" if "PROGRAM" in upper else "key_figures" if any(w in upper for w in ["DÉBOUCH", "DEBOUCH", "DURÉE", "DUREE"]) else "hero_editorial"
    label = VISUAL_THEMES[formation]["badge"]
    title_subject = topic or f"Nouvelle session {formation}"
    return {**DEFAULT_SLIDE, "formation": formation, "template": template, "category_label":"FORMATION PROFESSIONNELLE", "eyebrow": f"{formation} • POST RÉSEAUX", "title": title_subject[:90], "highlight_text": formation, "intro": f"Un contenu clair pour présenter {formation} avec une identité visuelle cohérente et premium.", "key_points":["Informations essentielles en un coup d’œil", "Format portrait prêt à publier", label.title()], "stats":[{"label":"Format","value":"1080×1350"},{"label":"Export","value":"PNG HD"},{"label":"Thème","value":formation}], "badges":[formation, label, "Charte verrouillée"], "cta":"Demander les informations"}


def session_to_social_prefill(session_data):
    formation = normalize_formation(session_data.get("formation") or session_data.get("display_name"))
    title = session_data.get("display_name") or session_data.get("formation") or f"Session {formation}"
    return {**DEFAULT_SLIDE, "formation": formation, "eyebrow": f"{formation} • SESSION", "title": str(title), "highlight_text": formation, "date": session_data.get("date_debut") or "", "location": session_data.get("lieu") or session_data.get("salle") or "", "duration": session_data.get("duration") or session_data.get("duree") or "", "price": session_data.get("prix") or "", "financing": session_data.get("financement") or "CPF / autres"}
