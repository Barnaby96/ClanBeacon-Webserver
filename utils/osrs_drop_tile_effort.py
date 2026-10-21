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

def estimate_raid_reward_expected_completions(purple_probability, target, conditional_reward_probability=1.0):
    """Expected raid completions for repeatable qualifying rewards."""
    from math import isfinite
    for name, probability in (("purple_probability", purple_probability), ("conditional_reward_probability", conditional_reward_probability)):
        if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not isfinite(probability) or not 0 < probability <= 1:
            raise ValueError(f"{name} must be a probability greater than zero and at most one")
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise ValueError("target must be a positive integer")
    return target / (purple_probability * conditional_reward_probability)

def estimate_raid_reward_completion_probability(purple_probability, target, raid_completions, conditional_reward_probability=1.0):
    """Probability of meeting a repeatable reward target within N raids."""
    from math import exp, fsum, isfinite, lgamma, log, log1p
    for name, value in (("purple_probability", purple_probability), ("conditional_reward_probability", conditional_reward_probability)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"{name} must be a probability greater than zero and at most one")
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise ValueError("target must be a positive integer")
    if isinstance(raid_completions, bool) or not isinstance(raid_completions, int) or raid_completions < 0:
        raise ValueError("raid_completions must be a non-negative integer")
    if target > raid_completions:
        return 0.0
    p = purple_probability * conditional_reward_probability
    if p == 1:
        return 1.0
    if p == 0:
        return 0.0
    n = raid_completions
    def mass(k):
        return exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + k * log(p) + (n - k) * log1p(-p))
    if target <= n - target + 1:
        result = 1.0 - fsum(mass(k) for k in range(target))
    else:
        result = fsum(mass(k) for k in range(target, n + 1))
    return max(0.0, min(1.0, result))

def estimate_raid_reward_probability_from_playtime(purple_probability, target, raids_per_hour, allocated_hours, conditional_reward_probability=1.0):
    """Estimate reward completion probability using available raiding time."""
    from decimal import ROUND_FLOOR
    from utils.osrs_procedural_effort_budget import estimate_activity_progress

    progress = estimate_activity_progress(raids_per_hour, allocated_hours)
    completions = int(progress.to_integral_value(rounding=ROUND_FLOOR))
    return estimate_raid_reward_completion_probability(
        purple_probability,
        target,
        completions,
        conditional_reward_probability=conditional_reward_probability,
    )

def estimate_raid_reward_probability_with_character_budgets(purple_probability, target, raids_per_hour, allocated_hours, budgets, previous_allocations_by_tile, participants, conditional_reward_probability=1.0):
    """Validate shared character-hours before estimating raid reward probability."""
    from utils.osrs_procedural_effort_budget import remaining_board_character_hours

    participant_ids = tuple(participants)
    if not participant_ids or len(set(participant_ids)) != len(participant_ids):
        raise ValueError("Raid participants must be non-empty and unique.")

    remaining = remaining_board_character_hours(budgets, previous_allocations_by_tile)
    remaining_board_character_hours(
        remaining,
        {"proposed_raid": {player: allocated_hours for player in participant_ids}},
    )

    return estimate_raid_reward_probability_from_playtime(
        purple_probability,
        target,
        raids_per_hour,
        allocated_hours,
        conditional_reward_probability=conditional_reward_probability,
    )
