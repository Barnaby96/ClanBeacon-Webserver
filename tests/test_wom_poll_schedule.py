"""Pure timing regressions for automatic WOM polling."""

from datetime import datetime, timedelta, timezone


def _utc(hour, minute=0):
    return datetime(
        2026, 10, 25,
        hour, minute,
        tzinfo=timezone.utc,
    )


def test_hourly_polling_transitions_to_final_countdown():
    from utils.wom_poll_schedule import (
        build_wom_poll_schedule,
    )

    starts_at = _utc(12)
    ends_at = _utc(17)

    schedule = build_wom_poll_schedule(
        starts_at,
        ends_at,
    )

    assert schedule == (
        _utc(12),
        _utc(13),
        _utc(14),
        _utc(15),
        _utc(16),
        _utc(16, 30),
        _utc(16, 45),
        _utc(16, 50),
        _utc(16, 55),
        _utc(17),
    )

    assert len(schedule) == len(set(schedule))


def test_non_aligned_start_and_end_keep_correct_milestones():
    from utils.wom_poll_schedule import (
        build_wom_poll_schedule,
    )

    schedule = build_wom_poll_schedule(
        _utc(12, 10),
        _utc(17, 20),
    )

    assert schedule == (
        _utc(12, 10),
        _utc(13, 10),
        _utc(14, 10),
        _utc(15, 10),
        _utc(16, 10),
        _utc(16, 20),
        _utc(16, 50),
        _utc(17, 5),
        _utc(17, 10),
        _utc(17, 15),
        _utc(17, 20),
    )


def test_short_competition_never_schedules_before_start():
    from utils.wom_poll_schedule import (
        build_wom_poll_schedule,
    )

    schedule = build_wom_poll_schedule(
        _utc(12),
        _utc(12, 25),
    )

    assert schedule == (
        _utc(12),
        _utc(12, 10),
        _utc(12, 15),
        _utc(12, 20),
        _utc(12, 25),
    )

    # Invalid or zero-length windows must not poll.
    assert build_wom_poll_schedule(
        _utc(12),
        _utc(12),
    ) == ()

    assert build_wom_poll_schedule(
        _utc(13),
        _utc(12),
    ) == ()


def test_poll_due_check_prevents_early_late_and_duplicate_runs():
    from utils.wom_poll_schedule import (
        get_due_wom_poll_slot,
    )

    starts_at = _utc(12)
    ends_at = _utc(17)

    def due(now, completed=()):
        return get_due_wom_poll_slot(
            starts_at,
            ends_at,
            now,
            completed_slots=completed,
        )

    # Never poll before Bingo starts.
    assert due(
        starts_at - timedelta(seconds=1)
    ) is None

    # Start-of-competition refresh.
    assert due(starts_at) == starts_at

    # Small scheduler delays are acceptable.
    assert due(
        starts_at + timedelta(seconds=30)
    ) == starts_at

    # The same slot cannot be processed twice.
    assert due(
        starts_at + timedelta(seconds=30),
        completed=(starts_at,),
    ) is None

    # Do not catch up with old missed poll slots.
    assert due(
        starts_at + timedelta(minutes=4)
    ) is None

    # Final countdown refresh.
    assert due(_utc(16, 55)) == _utc(16, 55)

    # One refresh at the deadline.
    assert due(ends_at) == ends_at

    assert due(
        ends_at + timedelta(seconds=30)
    ) == ends_at

    assert due(
        ends_at + timedelta(seconds=30),
        completed=(ends_at,),
    ) is None

    # No late backlog processing after competition end.
    assert due(
        ends_at + timedelta(minutes=4)
    ) is None
