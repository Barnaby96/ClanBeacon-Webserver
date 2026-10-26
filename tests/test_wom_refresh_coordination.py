from contextlib import contextmanager

import pytest

from utils import database, wom_tracking


def test_coordinator_processes_when_lock_available(monkeypatch):
    events = []
    result = {
        "competition_id": 151069,
        "metrics_processed": 2,
        "players_processed": 4,
        "tiles_completed": [],
        "errors": [],
    }

    @contextmanager
    def granted_lock():
        events.append("lock_acquired")
        try:
            yield True
        finally:
            events.append("lock_released")

    def fake_processor():
        events.append("processed")
        return result

    monkeypatch.setattr(
        database, "wom_refresh_lock", granted_lock
    )
    monkeypatch.setattr(
        wom_tracking,
        "process_wom_competition",
        fake_processor,
    )

    actual = wom_tracking.try_process_wom_competition()

    assert actual is result
    assert events == [
        "lock_acquired",
        "processed",
        "lock_released",
    ]


def test_coordinator_skips_when_lock_unavailable(monkeypatch):
    events = []

    @contextmanager
    def denied_lock():
        events.append("lock_denied")
        yield False

    def unexpected_processor():
        raise AssertionError(
            "WOM processing occurred without the lock."
        )

    monkeypatch.setattr(
        database, "wom_refresh_lock", denied_lock
    )
    monkeypatch.setattr(
        wom_tracking,
        "process_wom_competition",
        unexpected_processor,
    )

    actual = wom_tracking.try_process_wom_competition()

    assert actual is None
    assert events == ["lock_denied"]


def test_coordinator_releases_lock_on_processing_error(monkeypatch):
    events = []

    @contextmanager
    def granted_lock():
        events.append("lock_acquired")
        try:
            yield True
        finally:
            events.append("lock_released")

    def failing_processor():
        events.append("processing_error")
        raise ValueError("simulated WOM failure")

    monkeypatch.setattr(
        database, "wom_refresh_lock", granted_lock
    )
    monkeypatch.setattr(
        wom_tracking,
        "process_wom_competition",
        failing_processor,
    )

    with pytest.raises(ValueError, match="simulated WOM failure"):
        wom_tracking.try_process_wom_competition()

    assert events == [
        "lock_acquired",
        "processing_error",
        "lock_released",
    ]


def test_scheduled_refresh_claims_only_while_locked(monkeypatch):
    events = []
    scheduled_slot = (151069, "start", "end", "slot")
    result = {"competition_id": 151069}

    @contextmanager
    def granted_lock():
        events.append("acquired")
        try:
            yield True
        finally:
            events.append("released")

    def fake_claim(*args):
        assert args == scheduled_slot
        events.append("claimed")
        return True

    def fake_process():
        events.append("processed")
        return result

    monkeypatch.setattr(
        database, "wom_refresh_lock", granted_lock
    )
    monkeypatch.setattr(
        database, "claim_wom_poll_slot", fake_claim
    )
    monkeypatch.setattr(
        wom_tracking,
        "process_wom_competition",
        fake_process,
    )

    actual = wom_tracking.try_process_wom_competition(
        scheduled_slot=scheduled_slot
    )

    assert actual is result
    assert events == [
        "acquired",
        "claimed",
        "processed",
        "released",
    ]


def test_duplicate_scheduled_claim_skips_processing(monkeypatch):
    events = []

    @contextmanager
    def granted_lock():
        events.append("acquired")
        try:
            yield True
        finally:
            events.append("released")

    def fake_claim(*args):
        events.append("duplicate")
        return False

    def unexpected_process():
        raise AssertionError(
            "Duplicate WOM slot attempted processing."
        )

    monkeypatch.setattr(
        database, "wom_refresh_lock", granted_lock
    )
    monkeypatch.setattr(
        database, "claim_wom_poll_slot", fake_claim
    )
    monkeypatch.setattr(
        wom_tracking,
        "process_wom_competition",
        unexpected_process,
    )

    actual = wom_tracking.try_process_wom_competition(
        scheduled_slot=(151069, "start", "end", "slot")
    )

    assert actual is None
    assert events == [
        "acquired",
        "duplicate",
        "released",
    ]
