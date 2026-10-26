"""WOM Cog scheduling regressions without live WOM requests."""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from cogs.WOMCog import WOMCog


COMPETITION_ID = 151069


def _run_poll(
    monkeypatch,
    *,
    start=None,
    end=None,
    timing_present=True,
    claim_result=True,
    lock_acquired=True,
):
    calls = {
        "claims": [],
        "process": 0,
        "audit": 0,
    }

    timing = (
        {"starts_at": start, "ends_at": end}
        if timing_present
        else None
    )

    monkeypatch.setattr(
        "cogs.WOMCog.database.get_wom_competition_timing",
        lambda: timing,
    )
    monkeypatch.setattr(
        "cogs.WOMCog.database.get_wom_competition_id",
        lambda: COMPETITION_ID,
    )

    @contextmanager
    def fake_lock():
        yield lock_acquired

    monkeypatch.setattr(
        "cogs.WOMCog.database.wom_refresh_lock",
        fake_lock,
    )

    def fake_claim(competition_id, starts_at, ends_at, slot):
        calls["claims"].append(
            (competition_id, starts_at, ends_at, slot)
        )
        return claim_result

    monkeypatch.setattr(
        "cogs.WOMCog.database.claim_wom_poll_slot",
        fake_claim,
    )

    def fake_process():
        calls["process"] += 1
        return {
            "competition_id": COMPETITION_ID,
            "metrics_processed": 1,
            "players_processed": 1,
            "tiles_completed": [],
            "errors": [],
        }

    monkeypatch.setattr(
        "cogs.WOMCog.wom_tracking.process_wom_competition",
        fake_process,
    )

    def fake_audit(*args, **kwargs):
        calls["audit"] += 1

    monkeypatch.setattr(
        "cogs.WOMCog.database.record_wom_refresh_audit",
        fake_audit,
    )

    asyncio.run(
        WOMCog.wom_poll.coro(WOMCog(bot=None))
    )

    return calls


def test_no_polling_before_competition(monkeypatch):
    now = datetime.now(timezone.utc)

    calls = _run_poll(
        monkeypatch,
        start=now + timedelta(hours=1),
        end=now + timedelta(hours=6),
    )

    assert calls == {
        "claims": [],
        "process": 0,
        "audit": 0,
    }


def test_no_polling_after_competition(monkeypatch):
    now = datetime.now(timezone.utc)

    calls = _run_poll(
        monkeypatch,
        start=now - timedelta(hours=7),
        end=now - timedelta(minutes=5),
    )

    assert calls["claims"] == []
    assert calls["process"] == 0
    assert calls["audit"] == 0


def test_no_polling_between_scheduled_slots(monkeypatch):
    now = datetime.now(timezone.utc)

    calls = _run_poll(
        monkeypatch,
        start=now - timedelta(minutes=10),
        end=now + timedelta(hours=5),
    )

    assert calls["claims"] == []
    assert calls["process"] == 0


def test_no_polling_without_competition_timing(monkeypatch):
    calls = _run_poll(
        monkeypatch,
        timing_present=False,
    )

    assert calls["claims"] == []
    assert calls["process"] == 0


def test_polling_at_competition_start(monkeypatch):
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=10)
    end = start + timedelta(hours=5)

    calls = _run_poll(
        monkeypatch,
        start=start,
        end=end,
    )

    assert calls["process"] == 1
    assert calls["audit"] == 1
    assert len(calls["claims"]) == 1
    assert calls["claims"][0][0] == COMPETITION_ID
    assert calls["claims"][0][3] == start


def test_final_refresh_just_after_deadline(monkeypatch):
    now = datetime.now(timezone.utc)
    end = now - timedelta(seconds=20)
    start = end - timedelta(hours=5)

    calls = _run_poll(
        monkeypatch,
        start=start,
        end=end,
    )

    assert calls["process"] == 1
    assert calls["audit"] == 1
    assert len(calls["claims"]) == 1
    assert calls["claims"][0][3] == end


def test_duplicate_claim_prevents_second_refresh(monkeypatch):
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=10)

    calls = _run_poll(
        monkeypatch,
        start=start,
        end=start + timedelta(hours=5),
        claim_result=False,
    )

    assert len(calls["claims"]) == 1
    assert calls["process"] == 0
    assert calls["audit"] == 0


def test_scheduler_checks_every_thirty_seconds():
    assert WOMCog.wom_poll.seconds == 30.0


def test_lock_conflict_does_not_consume_poll_slot(monkeypatch):
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=10)

    calls = _run_poll(
        monkeypatch,
        start=start,
        end=start + timedelta(hours=5),
        lock_acquired=False,
    )

    assert calls == {
        "claims": [],
        "process": 0,
        "audit": 0,
    }
