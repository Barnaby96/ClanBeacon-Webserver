from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest


@pytest.mark.parametrize(
    "event_days, weekly_hours, expected_hours",
    [
        (7, 20, Decimal("16")),
        (14, 20, Decimal("32")),
        (7, 10, Decimal("8")),
        (3.5, 20, Decimal("8")),
    ],
)
def test_effective_character_hours_uses_duration_and_participation(
    event_days,
    weekly_hours,
    expected_hours,
):
    from utils.osrs_procedural_effort_budget import (
        calculate_effective_character_hours,
    )

    starts_at = datetime(
        2026, 11, 1, tzinfo=timezone.utc
    )
    ends_at = starts_at + timedelta(days=event_days)

    result = calculate_effective_character_hours(
        starts_at=starts_at,
        ends_at=ends_at,
        weekly_hours=weekly_hours,
    )

    assert result == expected_hours

@pytest.mark.parametrize(
    "character_hours, team_hours, global_hours, expected",
    [
        (None, None, 20, Decimal("20")),
        (None, None, 12.5, Decimal("12.5")),
        (None, 14, 20, Decimal("14")),
        (6, 14, 20, Decimal("6")),
        (0, 14, 20, Decimal("0")),
        (None, 0, 20, Decimal("0")),
        (None, None, 0, Decimal("0")),
    ],
)
def test_weekly_hours_override_precedence(
    character_hours,
    team_hours,
    global_hours,
    expected,
):
    from utils.osrs_procedural_effort_budget import (
        resolve_character_weekly_hours,
    )

    character_overrides = (
        {}
        if character_hours is None
        else {"main": character_hours}
    )
    team_overrides = (
        {}
        if team_hours is None
        else {"team_a": team_hours}
    )

    result = resolve_character_weekly_hours(
        character_id="main",
        team_id="team_a",
        character_overrides=character_overrides,
        team_overrides=team_overrides,
        global_weekly_hours=global_hours,
    )

    assert result == expected


def test_weekly_hours_ignores_unrelated_overrides():
    from utils.osrs_procedural_effort_budget import (
        resolve_character_weekly_hours,
    )

    result = resolve_character_weekly_hours(
        character_id="main",
        team_id="team_a",
        character_overrides={"other_character": 5},
        team_overrides={"other_team": 10},
        global_weekly_hours=20,
    )

    assert result == Decimal("20")

def test_negative_character_hours_rejected():
    from utils.osrs_procedural_effort_budget import resolve_character_weekly_hours
    with pytest.raises(ValueError):
        resolve_character_weekly_hours("main", "team_a", character_overrides={"main": -1})

@pytest.mark.parametrize("bad", [None, True, False, "invalid", float("nan"), float("inf")])
def test_invalid_character_hours_rejected(bad):
    from utils.osrs_procedural_effort_budget import resolve_character_weekly_hours
    with pytest.raises(ValueError):
        resolve_character_weekly_hours("main", "team_a", character_overrides={"main": bad})

def test_activity_progress_uses_allocated_hours_and_supplied_rate():
    from utils.osrs_procedural_effort_budget import estimate_activity_progress
    assert estimate_activity_progress(Decimal("12000"), Decimal("2.5")) == Decimal("30000")

@pytest.mark.parametrize("rate,hours", [(-1, 1), (1, -1), (float("nan"), 1), (1, float("inf")), (True, 1), (1, False)])
def test_activity_progress_rejects_invalid_inputs(rate, hours):
    from utils.osrs_procedural_effort_budget import estimate_activity_progress
    with pytest.raises(ValueError):
        estimate_activity_progress(rate, hours)
