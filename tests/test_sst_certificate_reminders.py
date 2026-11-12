import copy
from datetime import datetime, timedelta, timezone
import fcntl
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import sst_certificate_reminders as reminders


def session(identifier="aps", formation="APS", dates=("2026-11-10", "2026-11-12")):
    code = {"APS": {"uv": "UV1"}, "A3P": {"code": "UV1"},
            "AFC_APS_SSIAP": {"uv": "UV1", "afcCategory": "APS"},
            "SSIAP": {"uv": "SST-J1", "modality": "sst"}}[formation]
    planning = [{"date": day, "slots": [{"start": "08:30", "end": "12:30", "room": "Salle 1", **code},
                                       {"start": "13:30", "end": "16:30", "room": "Salle 1", **code}]}
                for day in dates]
    return {"id": identifier, "formation": formation, "name": "Une session", "steps": [],
            "a3pPlanningData" if formation == "A3P" else "apsPlanningData": planning}


def paris(day="2026-11-13", hour=9, minute=0):
    return datetime.fromisoformat(f"{day}T{hour:02}:{minute:02}:00").replace(tzinfo=reminders.PARIS)


class Delivery:
    def __init__(self, success=True):
        self.success = success
        self.batches = []

    def __call__(self, batch):
        self.batches.append(copy.deepcopy(batch))
        return self.success, None if self.success else "temporary_error"


def run(tmp_path, sessions, email, sms, now=None):
    return reminders.process_reminders(
        tmp_path, lambda: reminders.collect_sst_reminders(sessions), email, sms, now=now or paris(),
    )


def test_last_real_sst_day_sets_due_date_even_across_holiday_and_ignores_end_of_session():
    source = session()
    source.update(date_fin="2026-12-30", date_exam="2026-12-31", display_name="APS novembre")
    source["apsPlanningData"].append({"date": "2026-12-30", "slots": [{"uv": "UV2"}]})
    original = copy.deepcopy(source)
    result = reminders.collect_sst_reminders([source])
    assert len(result) == 1
    assert result[0] == {
        "key": "aps:2026-11-12", "session_id": "aps", "name": "APS novembre", "formation": "APS",
        "location": "Salle 1", "sst_dates_label": "10/11/2026 et 12/11/2026",
        "completed_on": "2026-11-12", "completed_on_label": "12/11/2026", "due_on": "2026-11-13",
    }
    assert source == original


@pytest.mark.parametrize("formation", ["APS", "A3P", "AFC_APS_SSIAP", "SSIAP"])
def test_supported_curricula_and_false_uv1_are_distinguished(formation):
    source = session(formation=formation)
    planning = source["a3pPlanningData" if formation == "A3P" else "apsPlanningData"]
    # Later unrelated modules must not delay the reminder.
    planning.append({"date": "2026-11-30", "slots": [{"code": "UV9", "uv": "UV9", "title": "Secourisme tactique d’urgence"}]})
    assert reminders.collect_sst_reminders([source])[0]["due_on"] == "2026-11-13"
    unrelated = {"id": "unrelated", "formation": "DESP", "apsPlanningData": [{"date": "2026-11-12", "slots": [{"uv": "UV1"}]}]}
    assert not reminders.collect_sst_reminders([unrelated])


def test_ssiap_needs_explicit_sst_and_afc_needs_aps_category():
    ssiap = {"id": "ssiap", "formation": "SSIAP", "apsPlanningData": [{"date": "2026-11-12", "slots": [{"uv": "UV1"}]}]}
    afc = {"id": "afc", "formation": "AFC_APS_SSIAP", "apsPlanningData": [{"date": "2026-11-12", "slots": [{"uv": "UV1", "afcCategory": "PAF"}]}]}
    assert not reminders.collect_sst_reminders([ssiap, afc])


def test_only_published_planning_counts_and_tactical_first_aid_is_not_sst():
    source = session(formation="A3P")
    source["a3pPlanningEditorDraft"] = source.pop("a3pPlanningData")
    source["a3pPlanningConfig"] = {"lockedModules": {"UV1": ["2026-11-10", "2026-11-12"]}}
    assert not reminders.collect_sst_reminders([source])
    source["a3pPlanningData"] = [{"date": "2026-11-12", "slots": [{"code": "UV9", "title": "Secourisme tactique d’urgence"}]}]
    assert not reminders.collect_sst_reminders([source])


@pytest.mark.parametrize("date_value", ["not-a-date", "2026-02-31", "", None])
def test_invalid_sst_date_never_produces_partial_completion(date_value):
    source = session(dates=("2026-11-10", date_value))
    assert not reminders.collect_sst_reminders([source])
    valid = session("valid")
    assert [r["session_id"] for r in reminders.collect_sst_reminders([source, valid])] == ["valid"]


@pytest.mark.parametrize("change", [
    {"archived": True}, {"cancelled": True}, {"canceled": True}, {"status": "annulée"},
    {"steps": [{"name": "Saisie des SST", "done": True}]},
])
def test_archived_cancelled_or_completed_sessions_are_excluded(change):
    source = session()
    source.update(change)
    assert not reminders.collect_sst_reminders([source])


def test_first_scan_initializes_before_9_and_keeps_todays_due_reminders(tmp_path):
    email, sms = Delivery(), Delivery()
    sources = [session(), session("old", dates=("2026-10-10", "2026-10-12"))]
    morning = run(tmp_path, sources, email, sms, paris(hour=8, minute=59))
    assert morning["initialized"] is True
    assert morning["activated_on"] == "2026-11-13"
    assert morning["eligible"] == 1
    assert morning["skipped_before_activation"] == 1
    assert not email.batches and not sms.batches
    due = run(tmp_path, sources, email, sms)
    assert due["initialized"] is False
    assert due["email_sent"] == due["sms_sent"] == 1
    assert [r["session_id"] for r in email.batches[0]] == ["aps"]
    assert sms.batches == email.batches


@pytest.mark.parametrize("day,utc_hour", [("2026-03-29", 7), ("2026-10-25", 8)])
def test_9am_follows_paris_dst_not_utc(day, utc_hour, tmp_path):
    completed = (datetime.fromisoformat(day).date() - timedelta(days=1)).isoformat()
    sources = [session(dates=(completed,))]
    email, sms = Delivery(), Delivery()
    instant = datetime.fromisoformat(f"{day}T{utc_hour:02}:00:00+00:00")
    assert not run(tmp_path, sources, email, sms, instant - timedelta(seconds=1))["email_sent"]
    assert run(tmp_path, sources, email, sms, instant)["email_sent"] == 1


def test_first_activation_at_9_sends_due_today_without_historical_blast(tmp_path):
    email, sms = Delivery(), Delivery()
    sources = [session(), session("old", dates=("2026-11-11",))]
    result = run(tmp_path, sources, email, sms)
    assert result["initialized"] and result["email_sent"] == result["sms_sent"] == 1
    assert result["skipped_before_activation"] == 1


def test_future_dates_are_not_sent_and_upcoming_is_sorted_and_bounded(tmp_path):
    email, sms = Delivery(), Delivery()
    sources = [session(str(n), dates=(f"2026-11-{n:02}",)) for n in range(20, 13, -1)]
    result = run(tmp_path, sources, email, sms)
    assert not email.batches and not sms.batches
    assert result["eligible"] == 0 and result["next_due_on"] == "2026-11-15"
    assert len(result["upcoming"]) == 5
    assert [r["due_on"] for r in result["upcoming"]] == sorted(r["due_on"] for r in result["upcoming"])
    assert all(set(r) == {"session_id", "formation", "completed_on", "due_on"} for r in result["upcoming"])


def test_downtime_catches_up_but_newly_discovered_historical_sessions_stay_excluded(tmp_path):
    email, sms = Delivery(), Delivery()
    run(tmp_path, [], email, sms, paris(hour=8))
    sources = [session(), session("later", dates=("2026-11-15",)), session("historical", dates=("2026-11-11",))]
    result = run(tmp_path, sources, email, sms, paris("2026-11-18"))
    assert result["email_sent"] == result["sms_sent"] == 2
    assert result["skipped_before_activation"] == 1
    assert len(email.batches) == 1
    assert [row["session_id"] for row in email.batches[0]] == ["aps", "later"]


def test_no_sending_after_18_and_next_morning_catches_up(tmp_path):
    email, sms = Delivery(), Delivery()
    assert not run(tmp_path, [session()], email, sms, paris(hour=18))["email_sent"]
    assert not run(tmp_path, [session()], email, sms, paris("2026-11-14", hour=8))["email_sent"]
    assert run(tmp_path, [session()], email, sms, paris("2026-11-14"))["email_sent"] == 1


def test_channel_failures_retry_after_30_minutes_without_duplicate_email(tmp_path):
    email, sms = Delivery(), Delivery(False)
    assert run(tmp_path, [session()], email, sms)["failed"] == 1
    status = reminders.inspect_delivery_state(tmp_path, ["aps:2026-11-12"])
    assert status["deliveries"]["aps:2026-11-12"]["email"]["sent_at"]
    assert status["deliveries"]["aps:2026-11-12"]["sms"]["sent_at"] is None
    assert run(tmp_path, [session()], email, sms, paris(minute=29))["failed"] == 0
    assert len(sms.batches) == 1
    sms.success = True
    result = run(tmp_path, [session()], email, sms, paris(minute=30))
    assert result["sms_sent"] == 1 and result["email_sent"] == 0
    assert len(email.batches) == 1 and len(sms.batches) == 2
    # A fresh process/callback pair still sees the durable successful delivery.
    restarted_email, restarted_sms = Delivery(), Delivery()
    assert run(tmp_path, [session()], restarted_email, restarted_sms, paris("2026-11-14"))["eligible"] == 0
    assert not restarted_email.batches and not restarted_sms.batches


def test_email_exception_does_not_block_sms_or_count_as_sent(tmp_path):
    def broken(_batch):
        raise OSError("transport unavailable")
    sms = Delivery()
    result = run(tmp_path, [session()], broken, sms)
    assert result["email_sent"] == 0 and result["sms_sent"] == 1 and result["failed"] == 1


def test_planning_relocation_before_due_is_read_again_and_new_end_date_wins(tmp_path):
    sources, email, sms = [session()], Delivery(), Delivery()
    run(tmp_path, sources, email, sms, paris(hour=8))
    sources[0]["apsPlanningData"][-1]["date"] = "2026-11-17"
    assert run(tmp_path, sources, email, sms)["eligible"] == 0
    result = run(tmp_path, sources, email, sms, paris("2026-11-18"))
    assert result["email_sent"] == result["sms_sent"] == 1
    assert email.batches[0][0]["completed_on"] == "2026-11-17"


@pytest.mark.parametrize("action", ["delete", "cancel", "done"])
def test_removing_cancelling_or_completing_after_initial_scan_cancels_pending(action, tmp_path):
    sources, email, sms = [session()], Delivery(), Delivery()
    run(tmp_path, sources, email, sms, paris(hour=8))
    if action == "delete":
        sources.clear()
    elif action == "cancel":
        sources[0]["status"] = "cancelled"
    else:
        sources[0]["steps"] = [{"name": "Saisie des SST", "done": True}]
    assert run(tmp_path, sources, email, sms)["eligible"] == 0
    assert not email.batches and not sms.batches


def test_lock_excludes_other_workers_even_during_transport_callback(tmp_path):
    sources, sms = [session()], Delivery()
    observed = []

    def email(_batch):
        observed.append(run(tmp_path, sources, Delivery(), Delivery()))
        return True, None

    assert run(tmp_path, sources, email, sms)["email_sent"] == 1
    assert observed[0]["busy"] is True
    with (tmp_path / (reminders.DATABASE_NAME + ".lock")).open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert run(tmp_path, sources, Delivery(), Delivery())["busy"] is True


def test_inspection_is_read_only_and_source_failure_does_not_activate(tmp_path):
    assert reminders.inspect_delivery_state(tmp_path / "missing", []) == {"activated_on": None, "deliveries": {}}
    assert not (tmp_path / "missing").exists()

    def unreadable():
        raise OSError("source unavailable")

    with pytest.raises(OSError):
        reminders.process_reminders(tmp_path, unreadable, Delivery(), Delivery(), now=paris())
    assert reminders.inspect_delivery_state(tmp_path, [])["activated_on"] is None
