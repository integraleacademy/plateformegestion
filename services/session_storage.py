"""Atomic, version-checked storage shared by all Gunicorn workers."""

from contextlib import contextmanager, nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import logging
import os
from pathlib import Path
import tempfile


logger = logging.getLogger(__name__)


class SessionStorageError(RuntimeError):
    """The persisted data cannot safely be read or changed."""


class SessionStorageConflict(SessionStorageError):
    """Another request saved a newer version of the document."""


class SessionSnapshot(dict):
    def __init__(self, value):
        super().__init__(value)
        self.original = deepcopy(value)


def _validate(value):
    if not isinstance(value, dict) or not isinstance(value.get("sessions"), list):
        raise SessionStorageError("Structure du fichier des sessions invalide.")
    if not isinstance(value.get("jurys", []), list):
        raise SessionStorageError("Structure du fichier des jurys invalide.")
    if any(not isinstance(row, dict) for key in ("sessions", "jurys") for row in value.get(key, [])):
        raise SessionStorageError("Enregistrement de session ou de jury invalide.")
    value.setdefault("jurys", [])
    return value


def _read(path, allow_missing):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return _validate(json.load(handle))
    except FileNotFoundError as exc:
        if allow_missing and not os.path.exists(path + ".bak"):
            return {"sessions": [], "jurys": []}
        raise SessionStorageError("Fichier des sessions introuvable ; restauration nécessaire.") from exc
    except (OSError, ValueError) as exc:
        logger.exception("SESSION_STORAGE_READ_FAILED path=%s; existing file preserved", path)
        raise SessionStorageError("Lecture des sessions impossible ; données conservées pour récupération.") from exc


@contextmanager
def _locked(path, exclusive=False):
    with open(path + ".lock", "a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_session_store(path, *, allow_missing=True):
    path = os.fspath(path)
    with _locked(path):
        return SessionSnapshot(_read(path, allow_missing))


def _atomic_write(path, payload):
    # A unique temporary file prevents another worker from truncating, renaming,
    # or continuing to write into this worker's newly installed live file.
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=os.path.dirname(path),
                                         prefix=".sessions-", suffix=".tmp", delete=False) as handle:
            temporary_path = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        directory_fd = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def save_session_store(path, data, *, allow_missing=True, reservation_guard=None):
    path = os.fspath(path)
    candidate = _validate(deepcopy(dict(data)))
    payload = _encode(candidate)  # Serialization failure must leave every file intact.
    with _locked(path, exclusive=True):
        current = _read(path, allow_missing)
        if candidate == current:
            if isinstance(data, SessionSnapshot):
                data.original = deepcopy(current)
            return
        if isinstance(data, SessionSnapshot):
            if candidate == data.original:
                return  # A read-only request must never undo a concurrent change.
            if current != data.original:
                raise SessionStorageConflict("Les sessions ont été modifiées ailleurs. Rechargez la page avant de réessayer.")
        elif os.path.exists(path):
            raise SessionStorageConflict("Rechargez les sessions avant de les enregistrer.")
        with (reservation_guard(current, candidate) if reservation_guard else nullcontext()):
            if os.path.exists(path):
                previous = Path(path).read_bytes()
                _atomic_write(path + ".bak", previous)
                # Retain the first valid version each day as well as the last version.
                # Nothing prunes these recovery points during an incident.
                directory = Path(path).parent / "sessions_backups"
                directory.mkdir(exist_ok=True)
                daily = directory / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".json")
                if not daily.exists():
                    _atomic_write(str(daily), previous)
            _atomic_write(path, payload)
            if isinstance(data, SessionSnapshot):
                data.original = deepcopy(candidate)



def storage_diagnostics(path):
    """Report counts and timestamps, never record contents or credentials."""
    path = Path(path)
    candidates = set(path.parent.glob("sessions*"))
    candidates.update((path.parent / "sessions_backups").glob("*.json"))
    result = []
    for candidate in sorted(candidates):
        if not candidate.is_file() or candidate.name.endswith(".lock"):
            continue
        stat = candidate.stat()
        row = {"file": str(candidate.relative_to(path.parent)), "bytes": stat.st_size,
               "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()}
        try:
            value = _read(str(candidate), False)
            row.update(sessions=len(value["sessions"]), jurys=len(value["jurys"]), valid=True)
        except SessionStorageError:
            row["valid"] = False
        result.append(row)
    return result
