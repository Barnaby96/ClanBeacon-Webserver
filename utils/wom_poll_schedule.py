"""Pure scheduling rules for automatic WOM competition polling.

The schedule is calculated from configured competition timing,
not from the bot's startup time.

This module does not make WOM requests or write to the database.
"""

from datetime import datetime, timedelta, timezone


POLL_TOLERANCE = timedelta(seconds=60)

FINAL_COUNTDOWN_MINUTES = (
    60,
    30,
    15,
    10,
    5,
    0,
)


def _as_utc(value):
    """Normalise an aware datetime to UTC.

    Naive or invalid timestamps remain unusable rather than
    being silently interpreted in the machine's local timezone.
    """
    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None or value.utcoffset() is None:
        return None

    return value.astimezone(timezone.utc)


def build_wom_poll_schedule(starts_at, ends_at):
    """Return ordered, unique polling slots for a competition.

    Poll once at the start, hourly during the main period,
    then at the final countdown milestones.

    No polling slots are created outside the competition.
    """
    start = _as_utc(starts_at)
    end = _as_utc(ends_at)

    if start is None or end is None or end <= start:
        return ()

    slots = {start}

    # Ordinary hourly polling ends when the final-hour
    # countdown begins. The T-60 slot is supplied by
    # the countdown schedule instead.
    final_hour_start = end - timedelta(hours=1)

    hourly_slot = start + timedelta(hours=1)

    while hourly_slot < final_hour_start:
        slots.add(hourly_slot)
        hourly_slot += timedelta(hours=1)

    # All countdown milestones are relative to the
    # configured competition end time.
    for minutes_remaining in FINAL_COUNTDOWN_MINUTES:
        slot = end - timedelta(
            minutes=minutes_remaining
        )

        if start <= slot <= end:
            slots.add(slot)

    return tuple(sorted(slots))


def get_due_wom_poll_slot(
    starts_at,
    ends_at,
    now,
    *,
    completed_slots=(),
):
    """Return the single scheduled slot currently due, if any.

    A slot is due for at most 60 seconds after its scheduled
    timestamp. Older missed slots are never replayed.

    The caller supplies completed slots so the scheduler
    can avoid refreshing the same milestone twice.

    Persisting completed slots across restarts is the
    responsibility of the eventual WOM Cog integration.
    """
    current_time = _as_utc(now)

    if current_time is None:
        return None

    schedule = build_wom_poll_schedule(
        starts_at,
        ends_at,
    )

    if not schedule:
        return None

    if completed_slots is None:
        completed_slots = ()

    try:
        completed = set()

        for completed_slot in completed_slots:
            normalised = _as_utc(completed_slot)

            if normalised is None:
                return None

            completed.add(normalised)

    except TypeError:
        return None

    # Work backwards so that we only consider the most
    # recent scheduled slot. This prevents API calls
    # being made to catch up with missed hourly slots.
    for slot in reversed(schedule):
        if slot > current_time:
            continue

        if current_time - slot > POLL_TOLERANCE:
            return None

        if slot in completed:
            return None

        return slot

    return None
