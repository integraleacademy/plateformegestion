import json
import multiprocessing
from pathlib import Path

import pytest

from services import session_storage as storage


def seed(path):
    data = {"sessions": [{"id": "one", "formation": "APS", "name": "Original"}], "jurys": [{"id": "jury-one"}]}
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


@pytest.mark.parametrize("raw", [b"", b'{"sessions": [', b'{"sessions": null}', b'[]', b'{}'])
def test_bad_store_is_never_treated_as_empty_or_overwritten(tmp_path, raw):
    path = tmp_path / "sessions.json"
    path.write_bytes(raw)
    for operation in (lambda: storage.load_session_store(path),
                      lambda: storage.save_session_store(path, {"sessions": [], "jurys": []})):
        with pytest.raises(storage.SessionStorageError):
            operation()
        assert path.read_bytes() == raw
    assert not Path(str(path) + ".bak").exists()


def test_missing_production_store_fails_closed(tmp_path):
    path = tmp_path / "sessions.json"
    with pytest.raises(storage.SessionStorageError):
        storage.load_session_store(path, allow_missing=False)
    with pytest.raises(storage.SessionStorageError):
        storage.save_session_store(path, {"sessions": []}, allow_missing=False)
    assert not path.exists()


def test_stale_requests_cannot_erase_changes_or_resurrect_deleted_sessions(tmp_path):
    path = tmp_path / "sessions.json"
    seed(path)
    stale = storage.load_session_store(path)
    fresh = storage.load_session_store(path)
    fresh["sessions"] = []
    storage.save_session_store(path, fresh)
    storage.save_session_store(path, stale)  # unchanged GET snapshot is a no-op
    assert json.loads(path.read_text())["sessions"] == []
    stale["sessions"][0]["name"] = "Concurrent rename"
    with pytest.raises(storage.SessionStorageConflict):
        storage.save_session_store(path, stale)
    assert json.loads(path.read_text())["sessions"] == []


def test_save_preserves_last_good_and_daily_backup_and_advances_snapshot(tmp_path):
    path = tmp_path / "sessions.json"
    initial = seed(path)
    snapshot = storage.load_session_store(path)
    snapshot["sessions"][0]["name"] = "First edit"
    storage.save_session_store(path, snapshot)
    assert json.loads(Path(str(path) + ".bak").read_text()) == initial
    first = json.loads(path.read_text())
    snapshot["sessions"][0]["name"] = "Second edit"
    storage.save_session_store(path, snapshot)
    assert json.loads(Path(str(path) + ".bak").read_text()) == first
    assert json.loads(next((tmp_path / "sessions_backups").glob("*.json")).read_text()) == initial
    assert snapshot.original == dict(snapshot)


def test_failed_live_replace_preserves_original_and_backup(tmp_path, monkeypatch):
    path = tmp_path / "sessions.json"
    seed(path)
    original = path.read_bytes()
    snapshot = storage.load_session_store(path)
    snapshot["sessions"][0]["name"] = "Updated"
    real_replace = storage.os.replace
    def fail_live(source, target):
        if str(target) == str(path):
            raise OSError("simulated disk error")
        return real_replace(source, target)
    monkeypatch.setattr(storage.os, "replace", fail_live)
    with pytest.raises(OSError, match="simulated disk error"):
        storage.save_session_store(path, snapshot)
    assert path.read_bytes() == original
    assert Path(str(path) + ".bak").read_bytes() == original
    assert not list(tmp_path.glob(".sessions-*.tmp"))


def _competing_writer(path, gate, results, name):
    snapshot = storage.load_session_store(path)
    snapshot["sessions"][0]["name"] = name
    gate.wait(timeout=10)
    try:
        storage.save_session_store(path, snapshot)
        results.put("saved")
    except storage.SessionStorageConflict:
        results.put("conflict")


def test_two_processes_keep_valid_json_and_detect_conflict(tmp_path):
    path = tmp_path / "sessions.json"
    initial = seed(path)
    context = multiprocessing.get_context("fork")
    gate, results = context.Barrier(2), context.Queue()
    workers = [context.Process(target=_competing_writer, args=(path, gate, results, name)) for name in ("A", "B")]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=15)
        assert worker.exitcode == 0
    assert sorted([results.get(timeout=2), results.get(timeout=2)]) == ["conflict", "saved"]
    saved = json.loads(path.read_text())
    assert saved["sessions"][0]["name"] in {"A", "B"}
    assert saved["jurys"] == initial["jurys"]
    assert json.loads(Path(str(path) + ".bak").read_text()) == initial


def test_serialization_error_leaves_data_and_backups_untouched(tmp_path):
    path = tmp_path / "sessions.json"
    seed(path)
    original = path.read_bytes()
    snapshot = storage.load_session_store(path)
    snapshot["sessions"][0]["invalid"] = object()
    with pytest.raises(TypeError):
        storage.save_session_store(path, snapshot)
    assert path.read_bytes() == original
    assert not Path(str(path) + ".bak").exists()


def test_sessions_page_is_read_only_and_storage_error_is_visible(tmp_path, monkeypatch):
    import app
    path = tmp_path / "sessions.json"
    path.write_text(json.dumps({"sessions": [], "jurys": []}), encoding="utf-8")
    monkeypatch.setattr(app, "SESSIONS_FILE", str(path))
    def fail_write(_):
        raise AssertionError("Opening the list must not save sessions")
    monkeypatch.setattr(app, "save_sessions", fail_write)
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        with client.session_transaction() as auth:
            auth["admin_logged"] = True
            auth["admin_session_version"] = app.ADMIN_SESSION_VERSION
        assert client.get("/sessions").status_code == 200
        path.write_bytes(b'{"sessions": [')
        response = client.get("/sessions")
        assert response.status_code == 503
        assert "momentanément indisponibles" in response.get_data(as_text=True)
        assert path.read_bytes() == b'{"sessions": ['
