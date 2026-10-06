from utils.osrs_tile_candidate_validation import assert_valid_tile_candidate_pool
from utils.board_generation import TrackingSource
from utils.osrs_generated_drop_tile_candidates import build_generated_drop_tile_candidates
from utils.osrs_generation_recipes import (
    StaticPointTargetModel,
    build_single_tile_candidate,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)
from utils.board_generation import TileCategory, canonical_id
from utils.osrs_pets import get_osrs_pet_options
from utils.osrs_tile_template_expansion import (
    get_static_drop_candidates,
    get_static_killcount_candidates,
    get_static_metric_candidates,
    get_static_skill_xp_candidates,
)
from utils.osrs_tile_templates import (
    make_drop_candidate,
    make_killcount_candidate,
    make_pet_candidate,
    make_skill_xp_candidate,
    make_skill_xp_or_pet_candidate,
)


def get_pet_source_from_option(option):
    label = option["label"]

    if " - " not in label:
        return option["value"]

    return label.split(" - ", 1)[0]


SPECIFIC_PET_TARGET_MODEL = StaticPointTargetModel(
    target_model_id="specific_pet_drop",
    target_by_point_value={
        5: 1,
    },
)


def build_pet_component_from_option(option):
    pet_name = option["value"]
    source_name = get_pet_source_from_option(
        option
    )

    return TileComponent(
        component_id=f"{pet_name}_pet",
        component_type=TileComponentType.PET,
        display_name=pet_name,
        tracking_source=TrackingSource.DINK,
        target_model_id="specific_pet_drop",
        metric_id=f"pet_{pet_name}",
        source_id=source_name,
        pet_id=pet_name,
        rng_level=4,
    )


def make_pet_candidate_from_option(option):
    pet_name = option["value"]
    component = build_pet_component_from_option(
        option
    )

    return build_single_tile_candidate(
        component,
        5,
        SPECIFIC_PET_TARGET_MODEL,
        title=f"Obtain {pet_name}",
        display_text=f"Obtain {pet_name}",
        explanation=(
            "Generated specific pet candidate from the OSRS pet option list.",
        ),
        include_generation_note=False,
    )

def get_curated_pet_candidates():
    return tuple(
        make_pet_candidate_from_option(
            option
        )
        for option in get_osrs_pet_options()
    )


CURATED_TILE_CANDIDATES = (
    *get_curated_pet_candidates(),
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



def get_curated_tile_generation_candidates():
    """Return candidates for generation previews.

    Killcount, drop, skill and metric entries are expanded from templates so
    the assembler can choose an appropriate point tier. Pet candidates still
    come from the curated static pet list.
    """

    expanded_candidate_categories = {
        TileCategory.KILLCOUNT,
        TileCategory.DROP,
    }

    pet_candidates = tuple(
        candidate
        for candidate in get_curated_tile_candidates()
        if candidate.primary_category == TileCategory.PET
    )

    remaining_static_candidates = tuple(
        candidate
        for candidate in get_curated_tile_candidates()
        if (
            candidate.primary_category not in expanded_candidate_categories
            and candidate.primary_category != TileCategory.PET
        )
    )

    from utils.osrs_composite_tile_catalogue import (
        get_curated_composite_tile_candidates,
    )

    return assert_valid_tile_candidate_pool(
        (
            *pet_candidates,
            *get_curated_composite_tile_candidates(),
            *get_static_metric_candidates(),
            *remaining_static_candidates,
            *get_static_killcount_candidates(),
            *build_generated_drop_tile_candidates(),
            *get_static_skill_xp_candidates(),
        )
    )


