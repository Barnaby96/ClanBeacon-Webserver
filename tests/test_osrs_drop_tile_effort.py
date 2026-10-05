from decimal import Decimal

import pytest

from utils.osrs_drop_tile_effort import (
    DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
    DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
    DROP_TILE_EFFORT_REASON_NO_GROUP_EXPECTED_ROLLS,
    DROP_TILE_EFFORT_REASON_UNPARSEABLE_DROP_RATE,
    estimate_group_unique_tile_effort,
    estimate_specific_drop_tile_effort_from_rate,
)


class FakeDropGroup:
    def estimate_expected_rolls_for_distinct_drop_target(self, target):
        if target == 2:
            return Decimal("250")

        return None


def test_specific_drop_effort_uses_representative_expected_rolls():
    estimate = estimate_specific_drop_tile_effort_from_rate(
        "1/512"
    )

    assert estimate.mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
    assert estimate.parseable is True
    assert estimate.expected_rolls == Decimal("512")
    assert estimate.total_effort == Decimal("512")


def test_specific_drop_effort_applies_access_and_difficulty_multipliers():
    estimate = estimate_specific_drop_tile_effort_from_rate(
        "1/512",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("2"),
    )

    assert estimate.expected_rolls == Decimal("512")
    assert estimate.total_effort == Decimal("1280.00")


def test_specific_drop_effort_marks_unparseable_rates():
    estimate = estimate_specific_drop_tile_effort_from_rate(
        "not a useful rate"
    )

    assert estimate.mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
    assert estimate.parseable is False
    assert estimate.expected_rolls is None
    assert estimate.total_effort is None
    assert estimate.reason == DROP_TILE_EFFORT_REASON_UNPARSEABLE_DROP_RATE


def test_group_unique_effort_uses_group_distinct_target_estimate():
    estimate = estimate_group_unique_tile_effort(
        FakeDropGroup(),
        2,
    )

    assert estimate.mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
    assert estimate.parseable is True
    assert estimate.expected_rolls == Decimal("250")
    assert estimate.total_effort == Decimal("250")


def test_group_unique_effort_marks_missing_group_estimates():
    estimate = estimate_group_unique_tile_effort(
        FakeDropGroup(),
        3,
    )

    assert estimate.mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
    assert estimate.parseable is False
    assert estimate.expected_rolls is None
    assert estimate.total_effort is None
    assert estimate.reason == DROP_TILE_EFFORT_REASON_NO_GROUP_EXPECTED_ROLLS


def test_effort_multipliers_must_be_positive():
    with pytest.raises(ValueError):
        estimate_specific_drop_tile_effort_from_rate(
            "1/512",
            source_difficulty_multiplier=0,
        )
