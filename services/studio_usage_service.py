"""Durable template usage, independent of projects and isolated per admin."""
import sqlite3
from pathlib import Path


def _connect(data_dir):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(Path(data_dir) / "studio_template_usage.sqlite3"), timeout=15)
    db.execute("""CREATE TABLE IF NOT EXISTS template_usage (
        admin TEXT NOT NULL, template_id TEXT NOT NULL,
        used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (admin, template_id))""")
    return db


def load_template_usage(data_dir, admin):
    db = _connect(data_dir)
    try:
        return dict(db.execute("SELECT template_id, used_at FROM template_usage WHERE admin = ?", (admin,)))
    finally:
        db.close()


def set_template_usage(data_dir, admin, template_id, used):
    db = _connect(data_dir)
    try:
        with db:
            if used:
                db.execute("INSERT OR IGNORE INTO template_usage (admin, template_id) VALUES (?, ?)", (admin, template_id))
            else:
                db.execute("DELETE FROM template_usage WHERE admin = ? AND template_id = ?", (admin, template_id))
        return dict(db.execute("SELECT template_id, used_at FROM template_usage WHERE admin = ?", (admin,)))
    finally:
        db.close()
