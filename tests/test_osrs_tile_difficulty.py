import pytest

from utils.osrs_tile_difficulty import (
    ContentDifficultyProfile,
    DifficultyTier,
    DropOrPetDifficultyProfile,
    DropRateProfile,
    compare_drop_or_pet_effort,
    expected_attempts_for_chance,
    expected_hours_for_chance,
    weighted_effort_score,
)


def test_expected_attempts_for_chance_uses_cumulative_probability():
    attempts = expected_attempts_for_chance(
        DropRateProfile(
            denominator=100
        ),
        0.5
    )

    assert attempts == 69


def test_expected_hours_uses_attempts_per_hour():
    profile = DropOrPetDifficultyProfile(
        item_id="example_pet",
        display_name="Example pet",
        drop_rate=DropRateProfile(
            denominator=100
        ),
        content=ContentDifficultyProfile(
            content_id="example",
            display_name="Example",
            attempts_per_hour=10,
            access_tier=DifficultyTier.LOW,
            mechanical_tier=DifficultyTier.LOW,
        ),
    )

    assert expected_hours_for_chance(
        profile,
        0.5
    ) == pytest.approx(
        6.9
    )


def test_weighted_effort_accounts_for_content_difficulty_not_just_drop_rate():
    easy_slow_rate = DropOrPetDifficultyProfile(
        item_id="beef",
        display_name="Beef",
        drop_rate=DropRateProfile(
            denominator=1000
        ),
        content=ContentDifficultyProfile(
            content_id="brutus",
            display_name="Brutus",
            attempts_per_hour=600,
            access_tier=DifficultyTier.LOW,
            mechanical_tier=DifficultyTier.VERY_LOW,
        ),
        rng_tier=DifficultyTier.HIGH,
    )

    hard_fast_rate = DropOrPetDifficultyProfile(
        item_id="smol_heredit",
        display_name="Smol heredit",
        drop_rate=DropRateProfile(
            denominator=200
        ),
        content=ContentDifficultyProfile(
            content_id="sol_heredit",
            display_name="Sol Heredit",
            attempts_per_hour=1,
            access_tier=DifficultyTier.VERY_HIGH,
            mechanical_tier=DifficultyTier.VERY_HIGH,
        ),
        rng_tier=DifficultyTier.MEDIUM,
    )

    assert weighted_effort_score(
        hard_fast_rate
    ) > weighted_effort_score(
        easy_slow_rate
    )

    assert compare_drop_or_pet_effort(
        easy_slow_rate,
        hard_fast_rate
    ) == -1


def test_drop_rate_profile_rejects_invalid_denominator():
    with pytest.raises(
        ValueError,
        match="positive"
    ):
        DropRateProfile(
            denominator=0
        )


def test_content_difficulty_rejects_invalid_attempt_rate():
    with pytest.raises(
        ValueError,
        match="Attempts per hour"
    ):
        ContentDifficultyProfile(
            content_id="bad",
            display_name="Bad",
            attempts_per_hour=0,
            access_tier=DifficultyTier.LOW,
            mechanical_tier=DifficultyTier.LOW,
        )


def test_expected_attempts_rejects_invalid_target_chance():
    with pytest.raises(
        ValueError,
        match="between 0 and 1"
    ):
        expected_attempts_for_chance(
            DropRateProfile(
                denominator=100
            ),
            1
        )
