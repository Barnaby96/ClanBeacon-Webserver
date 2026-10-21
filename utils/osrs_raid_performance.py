"""Explicit raid performance assumptions for procedural Bingo effort."""
from dataclasses import dataclass
from decimal import Decimal
from utils.osrs_drop_tile_effort import estimate_raid_reward_probability_from_playtime

@dataclass(frozen=True)
class RaidPerformanceProfile:
    source_id: str
    scenario: str
    raids_per_hour: float
    purple_probability: float

    def __post_init__(self):
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id is required")
        if not isinstance(self.scenario, str) or not self.scenario.strip():
            raise ValueError("scenario is required")
        for name in ("raids_per_hour", "purple_probability"):
            value = getattr(self, name)
            if isinstance(value, bool):
                raise ValueError(f"Invalid {name}")
            try:
                number = Decimal(str(value))
            except (ArithmeticError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid {name}") from error
            if not number.is_finite() or number <= 0:
                raise ValueError(f"Invalid {name}")
            if name == "purple_probability" and number > 1:
                raise ValueError("Purple probability cannot exceed one")

def estimate_raid_reward_probability_for_profile(profile, target, allocated_hours, conditional_reward_probability=1.0):
    return estimate_raid_reward_probability_from_playtime(
        profile.purple_probability, target, profile.raids_per_hour,
        allocated_hours, conditional_reward_probability=conditional_reward_probability,
    )

def compare_raid_reward_profiles(profiles, target, allocated_hours):
    """Rank raid scenarios by reward completion probability."""
    results = [
        (profile.source_id, estimate_raid_reward_probability_for_profile(profile, target, allocated_hours))
        for profile in profiles
    ]
    return tuple(sorted(results, key=lambda item: (-item[1], item[0])))
