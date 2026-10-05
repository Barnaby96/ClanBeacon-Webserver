from decimal import Decimal

from utils.osrs_drop_tile_source_effort import (
    get_drop_tile_source_effort_profile,
)


def test_known_source_effort_profile_applies_access_and_difficulty():
    profile = get_drop_tile_source_effort_profile(
        "unsired"
    )

    assert profile.access_requirement_multiplier == Decimal("2")
    assert profile.source_difficulty_multiplier == Decimal("1.5")
    assert "Abyssal Sire" in profile.reason


def test_unknown_source_effort_profile_defaults_to_neutral():
    profile = get_drop_tile_source_effort_profile(
        "simple_source"
    )

    assert profile.access_requirement_multiplier == Decimal("1")
    assert profile.source_difficulty_multiplier == Decimal("1")
    assert profile.reason == ""


def test_fortis_colosseum_source_effort_profile_marks_completion_rewards_as_hard():
    profile = get_drop_tile_source_effort_profile(
        "fortis_colosseum"
    )

    assert profile.access_requirement_multiplier == Decimal("5")
    assert profile.source_difficulty_multiplier == Decimal("500")
    assert "Wave 12" in profile.reason
