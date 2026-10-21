"""Difficulty-specific Bingo board generation rules."""
from dataclasses import replace
from utils.board_generation import BoardGenerationRules, TileCategory

_DIFFICULTY_PET_SETTINGS = {
    "relaxed": ((), (0, 1, 2)),
    "standard": ((), (1, 2, 3)),
    "competitive": ((5,), (2, 4, 6)),
    "brutal": ((3, 4, 5), (3, 5, 7)),
}

def build_board_generation_rules_for_difficulty(mode="competitive"):
    """Configure mandatory pet slots and secondary-pet limits."""
    if not isinstance(mode, str) or mode not in _DIFFICULTY_PET_SETTINGS:
        raise ValueError("Unknown Bingo difficulty mode.")

    pet_tiers, secondary_limits = _DIFFICULTY_PET_SETTINGS[mode]
    base = BoardGenerationRules()
    required = {tier: tuple(c for c in categories if c not in (TileCategory.SKILL, TileCategory.KILLCOUNT, TileCategory.DROP)) for tier, categories in base.required_categories_by_point.items()}
    flex = {tier: base.points_distribution[tier] - len(required[tier]) for tier in base.points_distribution}

    for tier in pet_tiers:
        if flex.get(tier, 0) < 1:
            raise ValueError("No flexible slot available for required pet.")
        required[tier] = (*required[tier], TileCategory.PET)
        flex[tier] -= 1

    count = len(pet_tiers)
    return replace(
        base,
        minimum_primary_categories_per_tier=2,
        target_primary_categories_per_tier=3,
        maximum_primary_category_tiles_per_tier=3,
        minimum_primary_category_counts={TileCategory.SKILL: 4, TileCategory.KILLCOUNT: 4, TileCategory.DROP: 4},
        required_categories_by_point=required,
        flex_slots_by_point=flex,
        primary_pet_tiles_min=count,
        primary_pet_tiles_target=count,
        primary_pet_tiles_max=count,
        secondary_pet_routes_min=secondary_limits[0],
        secondary_pet_routes_target=secondary_limits[1],
        secondary_pet_routes_max=secondary_limits[2],
    )

def classify_primary_pet_candidate(candidate):
    """Classify a known primary pet without changing board rules."""
    from utils.board_generation import PetRole
    from utils.osrs_pets import OSRS_PET_OPTIONS
    from utils.osrs_tile_templates import canonical_id
    if candidate.pet_role != PetRole.PRIMARY:
        return "other"
    pet_ids = {route.pet_id for route in candidate.routes if route.pet_id}
    if len(pet_ids) != 1:
        return "other"
    pet_id = next(iter(pet_ids))
    skill_sources = {"hunter", "woodcutting", "agility", "fishing", "runecraft", "mining", "thieving", "sailing", "farming"}
    skill_pets = {canonical_id(option["value"]) for option in OSRS_PET_OPTIONS if option["label"].partition(" - ")[0].lower() in skill_sources}
    if pet_id in skill_pets:
        return "skilling"
    boss_end = next((i for i, option in enumerate(OSRS_PET_OPTIONS) if option["value"] == "Baby chinchompa"), None)
    if boss_end is None:
        raise ValueError("Pet catalogue boss/skilling boundary is missing.")
    boss_pets = {canonical_id(option["value"]) for option in OSRS_PET_OPTIONS[:boss_end]}
    if pet_id in boss_pets:
        return "boss"
    return "other"
