"""Calculate available character-hours for procedural Bingo."""

from datetime import datetime
from decimal import Decimal


PARTICIPATION_FACTOR = Decimal("0.8")
SECONDS_PER_WEEK = Decimal("604800")


def calculate_effective_character_hours(
    starts_at,
    ends_at,
    weekly_hours=20,
):
    """Return expected character-hours during a Bingo event."""

    if not isinstance(starts_at, datetime):
        raise ValueError("starts_at must be a datetime.")

    if not isinstance(ends_at, datetime):
        raise ValueError("ends_at must be a datetime.")

    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise ValueError("starts_at must be timezone-aware.")

    if ends_at.tzinfo is None or ends_at.utcoffset() is None:
        raise ValueError("ends_at must be timezone-aware.")

    duration = ends_at - starts_at

    if duration.total_seconds() <= 0:
        raise ValueError("Event duration must be positive.")

    if isinstance(weekly_hours, bool):
        raise ValueError("Weekly hours must be non-negative.")

    try:
        hours_per_week = Decimal(str(weekly_hours))
    except Exception as error:
        raise ValueError(
            "Weekly hours must be numeric."
        ) from error

    if not hours_per_week.is_finite() or hours_per_week < 0:
        raise ValueError("Weekly hours must be non-negative.")

    duration_seconds = (
        Decimal(duration.days) * Decimal("86400")
        + Decimal(duration.seconds)
        + Decimal(duration.microseconds) / Decimal("1000000")
    )

    return (
        hours_per_week
        * duration_seconds
        / SECONDS_PER_WEEK
        * PARTICIPATION_FACTOR
    )

def resolve_character_weekly_hours(
    character_id,
    team_id,
    character_overrides=None,
    team_overrides=None,
    global_weekly_hours=20,
):
    """Resolve weekly hours using character, team, then global priority."""

    if character_overrides is None:
        character_overrides = {}

    if team_overrides is None:
        team_overrides = {}

    if character_id in character_overrides:
        weekly_hours = character_overrides[character_id]
    elif team_id in team_overrides:
        weekly_hours = team_overrides[team_id]
    else:
        weekly_hours = global_weekly_hours

    if isinstance(weekly_hours, bool):
        raise ValueError(
            "Weekly hours must be non-negative and numeric."
        )

    try:
        result = Decimal(str(weekly_hours))
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ValueError(
            "Weekly hours must be non-negative and numeric."
        ) from error

    if not result.is_finite() or result < 0:
        raise ValueError(
            "Weekly hours must be non-negative and numeric."
        )

    return result

def estimate_activity_progress(rate_per_hour, allocated_hours):
    """Estimate progress using a supplied rate and allocated hours."""
    if isinstance(rate_per_hour, bool) or isinstance(allocated_hours, bool):
        raise ValueError("Invalid activity rate or hours.")
    try:
        rate = Decimal(str(rate_per_hour))
        hours = Decimal(str(allocated_hours))
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ValueError("Invalid activity rate or hours.") from error
    if not rate.is_finite() or not hours.is_finite() or rate < 0 or hours < 0:
        raise ValueError("Invalid activity rate or hours.")
    return rate * hours

def remaining_board_character_hours(budgets, allocations_by_tile):
    """Track shared character-hours across Bingo tiles."""
    def valid_hours(value):
        if isinstance(value, bool):
            raise ValueError("Invalid character-hours.")
        try:
            result = Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError) as error:
            raise ValueError("Invalid character-hours.") from error
        if not result.is_finite() or result < 0:
            raise ValueError("Invalid character-hours.")
        return result

    remaining = {key: valid_hours(value) for key, value in budgets.items()}
    for allocations in allocations_by_tile.values():
        for key, value in allocations.items():
            if key not in remaining:
                raise ValueError("Unknown character allocation.")
            remaining[key] -= valid_hours(value)
            if remaining[key] < 0:
                raise ValueError("Allocation exceeds character-hours budget.")
    return remaining
