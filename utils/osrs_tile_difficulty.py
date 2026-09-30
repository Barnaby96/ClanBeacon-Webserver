"""Difficulty metadata helpers for generated OSRS Bingo tiles.

This module does not decide final board tiles yet. It provides the shared
metadata and scoring primitives that future drop/pet/template expansion can
use when assigning point tiers.
"""

from dataclasses import dataclass
from enum import Enum
import math


class DifficultyTier(Enum):
    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5


@dataclass(frozen=True)
class DropRateProfile:
    """Represents a simple 1/N drop chance per eligible attempt."""

    denominator: int

    def __post_init__(self):
        if self.denominator <= 0:
            raise ValueError(
                "Drop-rate denominator must be positive."
            )

    @property
    def probability_per_attempt(self):
        return 1 / self.denominator


@dataclass(frozen=True)
class ContentDifficultyProfile:
    """Difficulty/access metadata for a content source."""

    content_id: str
    display_name: str
    attempts_per_hour: float
    access_tier: DifficultyTier
    mechanical_tier: DifficultyTier
    notes: tuple = ()

    def __post_init__(self):
        if self.attempts_per_hour <= 0:
            raise ValueError(
                "Attempts per hour must be positive."
            )


@dataclass(frozen=True)
class DropOrPetDifficultyProfile:
    """Combined source + rate profile for a drop or pet candidate."""

    item_id: str
    display_name: str
    drop_rate: DropRateProfile
    content: ContentDifficultyProfile
    rng_tier: DifficultyTier = DifficultyTier.MEDIUM
    notes: tuple = ()


def expected_attempts_for_chance(drop_rate, target_chance):
    """Return attempts needed to reach a cumulative drop chance.

    Formula:
    chance = 1 - (1 - p)^attempts
    """

    if not 0 < target_chance < 1:
        raise ValueError(
            "Target chance must be between 0 and 1."
        )

    probability = drop_rate.probability_per_attempt

    return math.ceil(
        math.log(1 - target_chance)
        / math.log(1 - probability)
    )


def expected_hours_for_chance(profile, target_chance):
    attempts = expected_attempts_for_chance(
        profile.drop_rate,
        target_chance
    )

    return attempts / profile.content.attempts_per_hour


def weighted_effort_score(profile, target_chance=0.5):
    """Return a broad effort score for point-tier decisions.

    This intentionally combines expected time with access, mechanical and RNG
    weightings. It is not final balancing logic; it is a foundation for later
    tile scoring.
    """

    hours = expected_hours_for_chance(
        profile,
        target_chance
    )

    tier_multiplier = (
        profile.content.access_tier.value
        + profile.content.mechanical_tier.value
        + profile.rng_tier.value
    ) / 3

    return hours * tier_multiplier


def compare_drop_or_pet_effort(first, second, target_chance=0.5):
    first_score = weighted_effort_score(
        first,
        target_chance
    )
    second_score = weighted_effort_score(
        second,
        target_chance
    )

    if first_score < second_score:
        return -1

    if first_score > second_score:
        return 1

    return 0
