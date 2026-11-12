"""Read saved SST timetables and send durable, grouped certificate reminders.

No session is changed here. Email and SMS have separate delivery records, shared
by all workers on the persistent disk. Callbacks receive a list of reminders and
return ``(success, error)``; a successful callback acknowledges its whole batch.
"""

from datetime import date, datetime, timedelta, timezone
import fcntl
import logging
from pathlib import Path
import re
import sqlite3
import unicodedata
from zoneinfo import ZoneInfo

from services.session_location import training_location


logger = logging.getLogger("sst-certificates")
DATABASE_NAME = "sst_certificate_reminders.sqlite3"
PARIS = ZoneInfo("Europe/Paris")
RETRY_INTERVAL = timedelta(minutes=30)
CHANNELS = ("email", "sms")


def _token(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^A-Z0-9]", "", text.encode("ascii", "ignore").decode().upper())


def _flag(value):
    return value is True or value == 1 or str(value).strip().lower() in {"true", "yes", "oui"}


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            pass
    return None


def _formation(session):
    aliases = {
        "APS": "APS", "A3P": "A3P", "SSIAP": "SSIAP1", "SSIAP1": "SSIAP1",
        "AFCAPSSSIAP": "AFC_APS_SSIAP", "AFCAPSSSIAP1": "AFC_APS_SSIAP",
        "AFCCFRANCETRAVAILAPSSSIAP": "AFC_APS_SSIAP",
    }
    for field in ("training_code", "formation_type", "program_code", "formation"):
        if session.get(field):
            return aliases.get(_token(session[field]), "")
    return ""


def _excluded(session):
    if any(_flag(session.get(field)) for field in ("archived", "cancelled", "canceled")):
        return True
    if any(_token(session.get(field)) in {"CANCELLED", "CANCELED", "ANNULE", "ANNULEE"}
           for field in ("status", "state", "statut")):
        return True
    return any(
        isinstance(step, dict)
        and _token(step.get("name")) in {"SAISIEDESSST", "SAISIEDESCERTIFICATSSST"}
        and _flag(step.get("done"))
        for step in (session.get("steps") or [])
    )


def _sst_slot(formation, slot):
    if not isinstance(slot, dict):
        return False
    # A distant UV1 is not evidence that a practical SST course took place.
    if _token(slot.get("modality")) in {"ELEARNING", "DISTANCIEL", "DISTANCE", "REMOTE"}:
        return False
    if formation == "APS":
        return _token(slot.get("uv")) == "UV1"
    if formation == "A3P":
        return _token(slot.get("code") or slot.get("uv")) == "UV1"
    if formation == "AFC_APS_SSIAP":
        return _token(slot.get("afcCategory")) == "APS" and _token(slot.get("uv")) == "UV1"
    if formation == "SSIAP1":
        return (_token(slot.get("modality")) == "SST"
                or _token(slot.get("uv") or slot.get("code")) in {"SSTJ1", "SSTJ2"})
    return False


def collect_sst_reminders(sessions):
    """Return one reminder per saved session, due after its last SST day.

    Drafts and inferred schedules are deliberately excluded. If an SST day has
    an unreadable date, the whole session is skipped: an earlier valid day must
    never become a false completion date.
    """
    reminders = {}
    for session in sessions or []:
        if not isinstance(session, dict) or _excluded(session):
            continue
        identifier = str(session.get("id") or "").strip()
        formation = _formation(session)
        if not identifier or not formation:
            continue
        planning = session.get("a3pPlanningData" if formation == "A3P" else "apsPlanningData")
        if not isinstance(planning, list):
            continue
        dates, rooms = set(), set()
        invalid = False
        for day in planning:
            if not isinstance(day, dict) or not isinstance(day.get("slots", []), list):
                invalid = True
                break
            slots = [slot for slot in day.get("slots", []) if _sst_slot(formation, slot)]
            if not slots:
                continue
            training_day = _date(day.get("date"))
            if training_day is None:
                invalid = True
                break
            dates.add(training_day)
            rooms.update(str(slot.get("room") or day.get("room") or "").strip() for slot in slots)
        if invalid or not dates:
            continue
        ordered = sorted(dates)
        completed = ordered[-1]
        if completed == date.max:
            continue
        key = f"{identifier}:{completed.isoformat()}"
        reminders[key] = {
            "key": key,
            "session_id": identifier,
            "name": str(session.get("display_name") or session.get("name") or session.get("nom") or formation),
            "formation": formation,
            "location": " / ".join(sorted(rooms - {""})) or training_location(session),
            "sst_dates_label": " et ".join(day.strftime("%d/%m/%Y") for day in ordered),
            "completed_on": completed.isoformat(),
            "completed_on_label": completed.strftime("%d/%m/%Y"),
            "due_on": (completed + timedelta(days=1)).isoformat(),
        }
    return sorted(reminders.values(), key=lambda item: (item["due_on"], item["formation"], item["session_id"]))


def _connect(path):
    connection = sqlite3.connect(path, timeout=5)
    connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS deliveries (
            reminder_key TEXT NOT NULL,
            channel TEXT NOT NULL CHECK(channel IN ('email', 'sms')),
            last_attempt_at TEXT,
            sent_at TEXT,
            PRIMARY KEY (reminder_key, channel)
        )
    """)
    connection.commit()
    return connection


def _local_now(now):
    value = now if now is not None else datetime.now(PARIS)
    return value.replace(tzinfo=PARIS) if value.tzinfo is None else value.astimezone(PARIS)


def process_reminders(data_dir, load_reminders, send_email, send_sms, now=None):
    """Send due reminders between 09:00 and 18:00 Paris time, with catch-up.

    The first successful source read records an activation date, even before
    09:00. Earlier due dates stay excluded if old sessions are discovered later.
    Sent counts refer to reminder items, not transport calls (which are grouped).
    Failures are retried no sooner than 30 minutes, separately for each channel.
    """
    local_now = _local_now(now)
    utc_now = local_now.astimezone(timezone.utc)
    timestamp = utc_now.isoformat(timespec="seconds")
    today = local_now.date().isoformat()
    result = dict(initialized=False, activated_on=None, eligible=0, email_sent=0, sms_sent=0, failed=0,
                  busy=False, skipped_before_activation=0, next_due_on=None, upcoming=[])
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (DATABASE_NAME + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            result["busy"] = True
            return result
        connection = _connect(directory / DATABASE_NAME)
        try:
            # A source/storage failure must not be mistaken for an empty queue.
            loaded = load_reminders()
            if not isinstance(loaded, list):
                raise ValueError("The SST reminder source must return a list")
            reminders = sorted(
                {row["key"]: row for row in loaded
                 if isinstance(row, dict) and row.get("key") and _date(row.get("due_on"))}.values(),
                key=lambda row: (row["due_on"], row["session_id"]),
            )
            row = connection.execute("SELECT value FROM metadata WHERE key='activated_on'").fetchone()
            activated_on = row[0] if row else today
            if row is None:
                connection.execute("INSERT INTO metadata VALUES ('activated_on', ?)", (activated_on,))
                connection.commit()
                result["initialized"] = True
            result["activated_on"] = activated_on

            state = {(key, channel): (attempt, sent) for key, channel, attempt, sent in connection.execute(
                "SELECT reminder_key, channel, last_attempt_at, sent_at FROM deliveries"
            )}
            pending = []
            for reminder in reminders:
                if reminder["due_on"] < activated_on:
                    result["skipped_before_activation"] += 1
                    continue
                if all(state.get((reminder["key"], channel), (None, None))[1] for channel in CHANNELS):
                    continue
                pending.append(reminder)
            result["upcoming"] = [
                {key: row[key] for key in ("session_id", "formation", "completed_on", "due_on")}
                for row in pending[:5]
            ]
            result["next_due_on"] = pending[0]["due_on"] if pending else None
            due = [reminder for reminder in pending if reminder["due_on"] <= today]
            result["eligible"] = len(due)
            if not 9 <= local_now.hour < 18:
                return result

            for channel, callback in (("email", send_email), ("sms", send_sms)):
                batch = []
                for reminder in due:
                    attempted, sent = state.get((reminder["key"], channel), (None, None))
                    if sent:
                        continue
                    if attempted and utc_now - datetime.fromisoformat(attempted) < RETRY_INTERVAL:
                        continue
                    batch.append(reminder)
                if not batch:
                    continue
                # Persist attempts before networking, never mark a reminder as
                # sent until the transport reports acceptance.
                connection.executemany("""
                    INSERT INTO deliveries (reminder_key, channel, last_attempt_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(reminder_key, channel) DO UPDATE SET last_attempt_at=excluded.last_attempt_at
                """, [(row["key"], channel, timestamp) for row in batch])
                connection.commit()
                try:
                    success, _error = callback(batch)
                except Exception:
                    success = False
                    logger.exception("SST reminder transport failed channel=%s count=%s", channel, len(batch))
                if not success:
                    result["failed"] += len(batch)
                    logger.warning("SST reminders not accepted channel=%s count=%s", channel, len(batch))
                    continue
                connection.executemany(
                    "UPDATE deliveries SET sent_at=? WHERE reminder_key=? AND channel=?",
                    [(timestamp, row["key"], channel) for row in batch],
                )
                connection.commit()
                result[channel + "_sent"] += len(batch)
                for row in batch:
                    state[(row["key"], channel)] = (timestamp, timestamp)
                logger.info("SST reminders accepted channel=%s count=%s", channel, len(batch))
            remaining = [row for row in pending if not all(
                state.get((row["key"], channel), (None, None))[1] for channel in CHANNELS
            )]
            result["upcoming"] = [
                {key: row[key] for key in ("session_id", "formation", "completed_on", "due_on")}
                for row in remaining[:5]
            ]
            result["next_due_on"] = remaining[0]["due_on"] if remaining else None
            return result
        finally:
            connection.close()


def inspect_delivery_state(data_dir, keys):
    """Read delivery timestamps without creating files or triggering any work."""
    path = Path(data_dir) / DATABASE_NAME
    result = {"activated_on": None, "deliveries": {}}
    if not path.exists():
        return result
    wanted = set(keys)
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        row = connection.execute("SELECT value FROM metadata WHERE key='activated_on'").fetchone()
        result["activated_on"] = row[0] if row else None
        for key, channel, attempted, sent in connection.execute(
            "SELECT reminder_key, channel, last_attempt_at, sent_at FROM deliveries"
        ):
            if key in wanted:
                result["deliveries"].setdefault(key, {})[channel] = {
                    "last_attempt_at": attempted, "sent_at": sent,
                }
        return result
    finally:
        connection.close()
