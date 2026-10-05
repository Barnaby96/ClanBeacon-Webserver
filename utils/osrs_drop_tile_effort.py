from dataclasses import dataclass
from decimal import Decimal

from utils.osrs_drop_rate_metadata import parse_drop_rate


DROP_TILE_EFFORT_MODE_GROUP_UNIQUES = "group_uniques"
DROP_TILE_EFFORT_MODE_SPECIFIC_DROP = "specific_drop"

DROP_TILE_EFFORT_REASON_UNPARSEABLE_DROP_RATE = "unparseable_drop_rate"
DROP_TILE_EFFORT_REASON_NO_GROUP_EXPECTED_ROLLS = "no_group_expected_rolls"

DEFAULT_EFFORT_MULTIPLIER = Decimal("1")

DROP_TILE_POINT_TIER_EFFORT_THRESHOLDS = (
    (1, Decimal("100")),
    (2, Decimal("300")),
    (3, Decimal("750")),
    (4, Decimal("1500")),
    (5, Decimal("3000")),
)


@dataclass(frozen=True)
class DropTileEffortEstimate:
    mode: str
    expected_rolls: Decimal | None
    total_effort: Decimal | None
    parseable: bool
    reason: str = ""
    access_requirement_multiplier: Decimal = DEFAULT_EFFORT_MULTIPLIER
    source_difficulty_multiplier: Decimal = DEFAULT_EFFORT_MULTIPLIER


def normalise_effort_multiplier(value, label):
    multiplier = Decimal(str(value))

    if multiplier <= 0:
        raise ValueError(
            f"{label} must be greater than zero."
        )

    return multiplier


def apply_effort_multipliers(
    expected_rolls,
    access_requirement_multiplier=DEFAULT_EFFORT_MULTIPLIER,
    source_difficulty_multiplier=DEFAULT_EFFORT_MULTIPLIER,
):
    if expected_rolls is None:
        return None

    return (
        Decimal(expected_rolls)
        * normalise_effort_multiplier(
            access_requirement_multiplier,
            "access_requirement_multiplier",
        )
        * normalise_effort_multiplier(
            source_difficulty_multiplier,
            "source_difficulty_multiplier",
        )
    )


def build_drop_tile_effort_estimate(
    mode,
    expected_rolls,
    access_requirement_multiplier=DEFAULT_EFFORT_MULTIPLIER,
    source_difficulty_multiplier=DEFAULT_EFFORT_MULTIPLIER,
    parseable=True,
    reason="",
):
    access_requirement_multiplier = normalise_effort_multiplier(
        access_requirement_multiplier,
        "access_requirement_multiplier",
    )
    source_difficulty_multiplier = normalise_effort_multiplier(
        source_difficulty_multiplier,
        "source_difficulty_multiplier",
    )

    return DropTileEffortEstimate(
        mode=mode,
        expected_rolls=(
            Decimal(expected_rolls)
            if expected_rolls is not None
            else None
        ),
        total_effort=apply_effort_multipliers(
            expected_rolls,
            access_requirement_multiplier=access_requirement_multiplier,
            source_difficulty_multiplier=source_difficulty_multiplier,
        ),
        parseable=parseable,
        reason=reason,
        access_requirement_multiplier=access_requirement_multiplier,
        source_difficulty_multiplier=source_difficulty_multiplier,
    )


def estimate_specific_drop_tile_effort_from_rate(
    drop_rate,
    access_requirement_multiplier=DEFAULT_EFFORT_MULTIPLIER,
    source_difficulty_multiplier=DEFAULT_EFFORT_MULTIPLIER,
):
    estimate = parse_drop_rate(
        drop_rate
    )

    if (
        not estimate.parseable
        or estimate.representative_expected_rolls is None
    ):
        return build_drop_tile_effort_estimate(
            DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
            None,
            access_requirement_multiplier=access_requirement_multiplier,
            source_difficulty_multiplier=source_difficulty_multiplier,
            parseable=False,
            reason=DROP_TILE_EFFORT_REASON_UNPARSEABLE_DROP_RATE,
        )

    return build_drop_tile_effort_estimate(
        DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
        estimate.representative_expected_rolls,
        access_requirement_multiplier=access_requirement_multiplier,
        source_difficulty_multiplier=source_difficulty_multiplier,
    )


def estimate_group_unique_tile_effort(
    drop_group,
    target,
    access_requirement_multiplier=DEFAULT_EFFORT_MULTIPLIER,
    source_difficulty_multiplier=DEFAULT_EFFORT_MULTIPLIER,
):
    expected_rolls = drop_group.estimate_expected_rolls_for_distinct_drop_target(
        target
    )

    if expected_rolls is None:
        return build_drop_tile_effort_estimate(
            DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
            None,
            access_requirement_multiplier=access_requirement_multiplier,
            source_difficulty_multiplier=source_difficulty_multiplier,
            parseable=False,
            reason=DROP_TILE_EFFORT_REASON_NO_GROUP_EXPECTED_ROLLS,
        )

    return build_drop_tile_effort_estimate(
        DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
        expected_rolls,
        access_requirement_multiplier=access_requirement_multiplier,
        source_difficulty_multiplier=source_difficulty_multiplier,
    )


def suggest_drop_tile_point_value(
    total_effort,
    thresholds=DROP_TILE_POINT_TIER_EFFORT_THRESHOLDS,
):
    if total_effort is None:
        return None

    effort = Decimal(total_effort)

    for point_value, maximum_effort in thresholds:
        if effort <= maximum_effort:
            return point_value

    return thresholds[-1][0]
