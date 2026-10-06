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


def test_boss_source_effort_profiles_apply_access_and_difficulty_weighting():
    nex = get_drop_tile_source_effort_profile(
        "nex"
    )
    vorkath = get_drop_tile_source_effort_profile(
        "vorkath"
    )

    assert nex.access_requirement_multiplier == Decimal("2")
    assert nex.source_difficulty_multiplier == Decimal("25")
    assert "group-boss" in nex.reason

    assert vorkath.access_requirement_multiplier == Decimal("1.5")
    assert vorkath.source_difficulty_multiplier == Decimal("1.5")
    assert "quest access" in vorkath.reason


def test_wilderness_and_superior_slayer_source_effort_profiles_apply_weighting():
    wilderness = get_drop_tile_source_effort_profile(
        "wilderness_multi_source"
    )
    superior = get_drop_tile_source_effort_profile(
        "superior_slayer_monster"
    )

    assert wilderness.access_requirement_multiplier == Decimal("1.5")
    assert wilderness.source_difficulty_multiplier == Decimal("2")
    assert wilderness.minimum_point_value == 2
    assert "PvP risk" in wilderness.reason

    assert superior.access_requirement_multiplier == Decimal("2")
    assert superior.source_difficulty_multiplier == Decimal("1.5")
    assert superior.minimum_point_value == 4
    assert "superior spawn RNG" in superior.reason


def test_zalcano_source_effort_profile_accounts_for_song_of_the_elves_access():
    profile = get_drop_tile_source_effort_profile(
        "zalcano"
    )

    assert profile.access_requirement_multiplier == Decimal("1.5")
    assert profile.source_difficulty_multiplier == Decimal("1.5")
    assert "Song of the Elves" in profile.reason
    assert "Prifddinas" in profile.reason


def test_midgame_source_effort_profiles_apply_modest_weighting():
    royal_titans = get_drop_tile_source_effort_profile(
        "royal_titans"
    )
    hallowed_sepulchre = get_drop_tile_source_effort_profile(
        "hallowed_sepulchre"
    )
    lunar_chest = get_drop_tile_source_effort_profile(
        "lunar_chest"
    )

    assert royal_titans.access_requirement_multiplier == Decimal("1.25")
    assert royal_titans.source_difficulty_multiplier == Decimal("1.5")
    assert "boss-specific" in royal_titans.reason

    assert hallowed_sepulchre.access_requirement_multiplier == Decimal("1.5")
    assert hallowed_sepulchre.source_difficulty_multiplier == Decimal("1.25")
    assert "activity access" in hallowed_sepulchre.reason

    assert lunar_chest.access_requirement_multiplier == Decimal("1.25")
    assert lunar_chest.source_difficulty_multiplier == Decimal("1.25")
    assert "Varlamore" in lunar_chest.reason
