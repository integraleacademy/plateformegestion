"""Suivi durable des mails d'expiration, partagé entre les workers du service."""

import fcntl
import logging
import os
import re
import sqlite3
from datetime import datetime


logger = logging.getLogger("formateur-expiration")
DATABASE_NAME = "formateur_expiration_notifications.sqlite3"


def _connect(data_dir):
    connection = sqlite3.connect(os.path.join(data_dir, DATABASE_NAME), timeout=5)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            trainer_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            expiration TEXT NOT NULL,
            state TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            recipient TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (trainer_id, document_id, expiration)
        )
    """)
    connection.commit()
    return connection


def process_notifications(data_dir, load_expired_groups, send_notification):
    """Un envoi par formateur et par nouvelle échéance, avec reprise sur erreur.

    Le premier passage initialise les échéances déjà dépassées. Les prochaines
    expirations sont ensuite notifiées, indépendamment des consultations.
    Le verrou couvre la lecture, l'envoi et son enregistrement : deux workers
    ne peuvent pas envoyer la même notification en parallèle.
    """
    os.makedirs(data_dir, exist_ok=True)
    result = dict(initialized=False, baseline=0, sent=0, documents=0, failed=0, busy=False)
    lock_path = os.path.join(data_dir, DATABASE_NAME + ".lock")
    with open(lock_path, "a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            result["busy"] = True
            return result

        connection = _connect(data_dir)
        try:
            groups = load_expired_groups()
            now = datetime.now().isoformat(timespec="seconds")
            initialized = connection.execute(
                "SELECT value FROM metadata WHERE key = 'initialized_at'"
            ).fetchone()
            if not initialized:
                for group in groups:
                    for doc in group["documents"]:
                        connection.execute(
                            "INSERT OR IGNORE INTO notifications VALUES (?, ?, ?, 'baseline', ?, '')",
                            (group["id"], doc["id"], doc["expiration"], now),
                        )
                        result["baseline"] += 1
                connection.execute("INSERT INTO metadata VALUES ('initialized_at', ?)", (now,))
                connection.commit()
                result["initialized"] = True
                logger.info("Initialized expiration notifications baseline_documents=%s", result["baseline"])
                return result

            for group in groups:
                documents = [
                    doc for doc in group["documents"]
                    if not connection.execute(
                        "SELECT 1 FROM notifications WHERE trainer_id=? AND document_id=? AND expiration=?",
                        (group["id"], doc["id"], doc["expiration"]),
                    ).fetchone()
                ]
                if not documents:
                    continue
                recipient = (group.get("email") or "").strip()
                if not re.fullmatch(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+", recipient):
                    result["failed"] += 1
                    logger.warning("Expiration notification skipped trainer_id=%s reason=invalid_email", group["id"])
                    continue

                try:
                    success, error = send_notification({**group, "email": recipient}, documents)
                except Exception:
                    success, error = False, "unexpected_error"
                    logger.exception("Expiration notification failed trainer_id=%s", group["id"])
                if not success:
                    result["failed"] += 1
                    logger.warning("Expiration notification not sent trainer_id=%s reason=%s", group["id"], error)
                    continue

                sent_at = datetime.now().isoformat(timespec="seconds")
                for doc in documents:
                    connection.execute(
                        "INSERT INTO notifications VALUES (?, ?, ?, 'sent', ?, ?)",
                        (group["id"], doc["id"], doc["expiration"], sent_at, recipient),
                    )
                # Chaque mail réussi est enregistré avant de passer au suivant.
                connection.commit()
                result["sent"] += 1
                result["documents"] += len(documents)
                logger.info("Expiration notification sent trainer_id=%s documents=%s", group["id"], len(documents))
            return result
        finally:
            connection.close()


def last_notification_at(data_dir, trainer_id):
    database = os.path.join(data_dir, DATABASE_NAME)
    if not os.path.exists(database):
        return ""
    try:
        connection = sqlite3.connect(database, timeout=1)
        try:
            row = connection.execute(
                "SELECT MAX(recorded_at) FROM notifications WHERE trainer_id=? AND state='sent'",
                (trainer_id,),
            ).fetchone()
        finally:
            connection.close()
        return (row[0] if row else "") or ""
    except sqlite3.OperationalError:
        return ""
