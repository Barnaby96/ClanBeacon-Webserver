from utils.board_generation import TileCategory
from utils.osrs_tile_templates import (
    make_drop_candidate,
    make_killcount_candidate,
    make_pet_candidate,
    make_skill_xp_candidate,
    make_skill_xp_or_pet_candidate,
)


CURATED_TILE_CANDIDATES = (
    make_pet_candidate(
        title="Obtain any skilling pet",
        point_value=4,
        pet_group_id="skilling_pets",
        source_id="skilling_pets",
        display_text="Obtain any skilling pet",
        additional_hard_unique_tags=(
            "source:any_pet",
        ),
        explanation=(
            "Primary pet-led tile.",
            "Consumes skilling pets and the broad any-pet source.",
        ),
    ),
    make_pet_candidate(
        title="Obtain any pet",
        point_value=5,
        pet_group_id="any_pet",
        source_id="any_pet",
        display_text="Obtain any pet",
        explanation=(
            "Primary pet-led chaos tile.",
            "Consumes the broad any-pet source.",
        ),
    ),
    make_skill_xp_candidate(
        title="Gain 500,000 Cooking XP",
        point_value=1,
        skill_id="cooking",
        xp_target=500_000,
        explanation=(
            "Simple WOM-tracked skill XP tile.",
            "Consumes Cooking for board uniqueness.",
        ),
    ),
    make_skill_xp_candidate(
        title="Gain 500,000 Firemaking XP",
        point_value=1,
        skill_id="firemaking",
        xp_target=500_000,
        explanation=(
            "Simple WOM-tracked skill XP tile.",
            "Consumes Firemaking for board uniqueness.",
        ),
    ),
    make_skill_xp_candidate(
        title="Gain 750,000 Fletching XP",
        point_value=2,
        skill_id="fletching",
        xp_target=750_000,
        explanation=(
            "Simple WOM-tracked skill XP tile.",
            "Consumes Fletching for board uniqueness.",
        ),
    ),
    make_skill_xp_candidate(
        title="Gain 750,000 Crafting XP",
        point_value=2,
        skill_id="crafting",
        xp_target=750_000,
        explanation=(
            "Simple WOM-tracked skill XP tile.",
            "Consumes Crafting for board uniqueness.",
        ),
    ),
    make_killcount_candidate(
        title="Complete 150 Zulrah KC",
        point_value=3,
        boss_id="zulrah",
        target=150,
        content_id="zulrah",
        explanation=(
            "WOM-tracked Zulrah KC tile.",
            "Uses Zulrah content access, which resolves through Regicide.",
        ),
    ),
    make_drop_candidate(
        title="Obtain any Zulrah unique",
        point_value=3,
        source_id="zulrah",
        boss_id="zulrah",
        drop_group_id="zulrah_uniques",
        content_id="zulrah",
        display_text="Obtain any Zulrah unique",
        explanation=(
            "Dink-tracked Zulrah drop tile.",
            "Conflicts with other Zulrah-source tiles when assembling a board.",
        ),
    ),
    make_killcount_candidate(
        title="Complete 150 Vorkath KC",
        point_value=4,
        boss_id="vorkath",
        target=150,
        content_id="vorkath",
        explanation=(
            "WOM-tracked Vorkath KC tile.",
            "Uses Vorkath content access, which resolves through Dragon Slayer II.",
        ),
    ),
    make_drop_candidate(
        title="Obtain any Vorkath unique",
        point_value=4,
        source_id="vorkath",
        boss_id="vorkath",
        drop_group_id="vorkath_uniques",
        content_id="vorkath",
        display_text="Obtain any Vorkath unique",
        explanation=(
            "Dink-tracked Vorkath drop tile.",
            "Conflicts with other Vorkath-source tiles when assembling a board.",
        ),
    ),
    make_skill_xp_or_pet_candidate(
        title="Gain 1,000,000 Thieving XP OR obtain Rocky",
        point_value=3,
        skill_id="thieving",
        xp_target=1_000_000,
        pet_id="rocky",
        explanation=(
            "WOM-tracked XP route with Dink-tracked pet shortcut.",
            "Consumes Thieving and Rocky for board uniqueness.",
        ),
    ),
    make_skill_xp_or_pet_candidate(
        title="Gain 1,000,000 Fishing XP OR obtain Heron",
        point_value=3,
        skill_id="fishing",
        xp_target=1_000_000,
        pet_id="heron",
        explanation=(
            "WOM-tracked XP route with Dink-tracked pet shortcut.",
            "Consumes Fishing and Heron for board uniqueness.",
        ),
    ),
    make_skill_xp_or_pet_candidate(
        title="Gain 1,000,000 Mining XP OR obtain Rock golem",
        point_value=3,
        skill_id="mining",
        xp_target=1_000_000,
        pet_id="rock_golem",
        explanation=(
            "WOM-tracked XP route with Dink-tracked pet shortcut.",
            "Consumes Mining and Rock golem for board uniqueness.",
        ),
    ),
    make_skill_xp_or_pet_candidate(
        title="Gain 1,000,000 Runecraft XP OR obtain Rift guardian",
        point_value=4,
        skill_id="runecraft",
        xp_target=1_000_000,
        pet_id="rift_guardian",
        explanation=(
            "WOM-tracked XP route with Dink-tracked pet shortcut.",
            "Consumes Runecraft and Rift guardian for board uniqueness.",
        ),
    ),
)


def get_curated_tile_candidates():
    return CURATED_TILE_CANDIDATES


def get_curated_tile_candidates_by_category(category):
    return tuple(
        candidate
        for candidate in CURATED_TILE_CANDIDATES
        if candidate.primary_category == category
    )


def get_curated_skill_led_candidates():
    return get_curated_tile_candidates_by_category(
        TileCategory.SKILL
    )


def get_curated_killcount_led_candidates():
    return get_curated_tile_candidates_by_category(
        TileCategory.KILLCOUNT
    )


def get_curated_drop_led_candidates():
    return get_curated_tile_candidates_by_category(
        TileCategory.DROP
    )
