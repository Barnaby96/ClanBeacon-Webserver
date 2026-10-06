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


def test_slayer_boss_source_effort_profiles_apply_task_access_weighting():
    hydra = get_drop_tile_source_effort_profile(
        "alchemical_hydra"
    )
    araxxor = get_drop_tile_source_effort_profile(
        "araxxor"
    )

    assert hydra.access_requirement_multiplier == Decimal("2")
    assert hydra.source_difficulty_multiplier == Decimal("1.5")
    assert "Slayer" in hydra.reason
    assert "task" in hydra.reason

    assert araxxor.access_requirement_multiplier == Decimal("2")
    assert araxxor.source_difficulty_multiplier == Decimal("1.75")
    assert "Slayer" in araxxor.reason
    assert "task" in araxxor.reason
