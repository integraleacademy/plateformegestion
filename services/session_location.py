"""Change a session's main venue without rebuilding its saved timetable."""

DEFAULT_TRAINING_LOCATION = "Intégrale Academy – 54 chemin du Carreou – 83480 PUGET-SUR-ARGENS"


def training_location(session):
    if str(session.get("formation") or "").upper() == "A3P":
        room = session.get("a3pRoom") or session.get("salle") or session.get("room")
        if not room:
            state = session.get("a3pPlanningBuilder") or session.get("a3pPlanningDraftJson") or {}
            if isinstance(state, dict):
                room = (state.get("scheduleConfig") or state).get("room")
    else:
        room = session.get("salle") or session.get("room")
    return str(room or DEFAULT_TRAINING_LOCATION).strip()


def validate_training_location(value):
    if not isinstance(value, str):
        raise ValueError("Veuillez renseigner le lieu de formation.")
    value = " ".join(value.split())
    if not value:
        raise ValueError("Veuillez renseigner le lieu de formation.")
    if len(value) > 300:
        raise ValueError("Le lieu de formation doit contenir au maximum 300 caractères.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Le lieu de formation contient un caractère invalide.")
    return value


def update_training_location(session, value):
    """Only replace inherited/main rooms; keep remote, exam and special rooms."""
    value = validate_training_location(value)
    previous = training_location(session)
    if value == previous:
        return False

    def update_rows(rows):
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("exam") or row.get("isExam"):
                continue
            modality = str(row.get("modality") or "").lower()
            if modality in {"elearning", "e-learning", "distanciel", "remote", "examen", "exam"}:
                continue
            category = str(row.get("afcCategory") or row.get("category") or row.get("uv") or row.get("code") or "").upper()
            if category.startswith(("EXAM", "EXAMEN")) or str(row.get("part") or "").upper().startswith("EXAMEN"):
                continue
            if isinstance(row.get("slots"), list):
                update_rows(row["slots"])
            # Never add fields to day records or change dates/hours/modules.
            if "room" in row or ("start" in row and "end" in row):
                room = str(row.get("room") or "").strip()
                if not room or room == previous:
                    row["room"] = value

    def update_config(state):
        if not isinstance(state, dict):
            return
        state["room"] = value
        update_rows(state.get("days"))
        locked = state.get("lockedModules")
        if isinstance(locked, dict):
            for rows in locked.values():
                update_rows(rows)

    session["salle"] = value
    session["room"] = value
    update_rows(session.get("apsPlanningData"))
    if str(session.get("formation") or "").upper() == "A3P":
        session["a3pRoom"] = value
        for key in ("a3pPlanningData", "a3pPlanningEditorDraft"):
            update_rows(session.get(key))
        for key in ("a3pPlanningBuilder", "a3pPlanningDraftJson"):
            state = session.get(key)
            if isinstance(state, dict):
                update_config(state.get("scheduleConfig") if isinstance(state.get("scheduleConfig"), dict) else state)
                for planning_key in ("preview", "planning", "generatedPlanning"):
                    update_rows(state.get(planning_key))
        manual = session.get("a3pTrainerManualModulesData")
        if isinstance(manual, dict):
            for rows in manual.values():
                update_rows(rows)
        if session.get("a3pPlanningData"):
            session["trainingLocationPdfPending"] = True
    elif session.get("apsPlanningData"):
        session["trainingLocationPdfPending"] = True
    return True
