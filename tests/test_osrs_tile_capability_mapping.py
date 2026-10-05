from utils.board_generation import (
    ContributionMode,
    Route,
    TileCategory,
    TrackingSource,
)
from utils.osrs_tile_capability_mapping import (
    get_capability_score_field_for_route,
    get_capability_score_field_for_source_id,
    get_primary_capability_score_field_for_candidate,
)
from utils.osrs_tile_template_expansion import (
    STATIC_DROP_TEMPLATES,
    expand_drop_template,
)


def route_for_static_drop_group(drop_group_id):
    template = next(
        template
        for template in STATIC_DROP_TEMPLATES
        if template.drop_group_id == drop_group_id
    )

    return expand_drop_template(
        template
    )[0].routes[0]


def candidate_for_static_drop_group(drop_group_id):
    template = next(
        template
        for template in STATIC_DROP_TEMPLATES
        if template.drop_group_id == drop_group_id
    )

    return expand_drop_template(
        template
    )[0]


def test_source_ids_map_to_team_builder_capability_fields():
    assert get_capability_score_field_for_source_id(
        "zulrah"
    ) == "solo_boss_score"
    assert get_capability_score_field_for_source_id(
        "kraken"
    ) == "slayer_boss_score"
    assert get_capability_score_field_for_source_id(
        "duke_sucellus"
    ) == "dt2_boss_score"
    assert get_capability_score_field_for_source_id(
        "chambers_of_xeric"
    ) == "raid_score"
    assert get_capability_score_field_for_source_id(
        "wilderness"
    ) == "wilderness_boss_score"


def test_static_drop_routes_map_to_capability_fields():
    assert get_capability_score_field_for_route(
        route_for_static_drop_group(
            "zulrah_uniques"
        )
    ) == "solo_boss_score"

    assert get_capability_score_field_for_route(
        route_for_static_drop_group(
            "kraken_unique"
        )
    ) == "slayer_boss_score"

    assert get_capability_score_field_for_route(
        route_for_static_drop_group(
            "barrows_brothers_unique"
        )
    ) == "midgame_boss_score"

    assert get_capability_score_field_for_route(
        route_for_static_drop_group(
            "wilderness_ring"
        )
    ) == "wilderness_boss_score"


def test_skill_route_maps_to_skilling_score():
    route = Route(
        route_type=TileCategory.SKILL,
        display_text="Gain XP",
        target=100000,
        tracking_source=next(iter(TrackingSource)),
        contribution_mode=ContributionMode.TEAM_SUM,
        skill_id="thieving",
    )

    assert get_capability_score_field_for_route(
        route
    ) == "skilling_score"


def test_candidate_maps_to_single_primary_capability_field():
    assert get_primary_capability_score_field_for_candidate(
        candidate_for_static_drop_group(
            "zulrah_uniques"
        )
    ) == "solo_boss_score"


def test_unknown_route_has_no_capability_field():
    route = Route(
        route_type=TileCategory.DROP,
        display_text="Obtain unknown item",
        target=1,
        tracking_source=TrackingSource.DINK,
        contribution_mode=ContributionMode.TEAM_SUM,
        source_id="unknown_source",
    )

    assert get_capability_score_field_for_route(
        route
    ) is None


def test_combined_source_ids_map_when_parts_share_same_capability_field():
    assert get_capability_score_field_for_source_id(
        "chaos_elemental_/_chaos_fanatic"
    ) == "wilderness_boss_score"


def test_combined_source_ids_do_not_map_when_parts_have_different_fields():
    assert get_capability_score_field_for_source_id(
        "zulrah_/_kraken"
    ) is None


def test_pet_source_aliases_map_to_capability_fields():
    assert get_capability_score_field_for_source_id(
        "royal_titans"
    ) == "group_boss_score"

    assert get_capability_score_field_for_source_id(
        "ice_inferno"
    ) == "endgame_boss_score"

    assert get_capability_score_field_for_source_id(
        "master_clue_scrolls"
    ) == "clue_activity_score"


def test_skilling_pet_sources_map_to_skilling_score():
    for source_id in (
        "agility",
        "farming",
        "fishing",
        "herbiboars",
        "hunter",
        "hunter_guild_rumours",
        "mining",
        "runecraft",
        "sailing",
        "thieving",
        "woodcutting",
    ):
        assert get_capability_score_field_for_source_id(
            source_id
        ) == "skilling_score"


def test_refreshed_pet_source_aliases_map_to_capability_fields():
    assert get_capability_score_field_for_source_id(
        "inferno"
    ) == "endgame_boss_score"

    assert get_capability_score_field_for_source_id(
        "tzhaar_fight_cave"
    ) == "midgame_boss_score"

    assert get_capability_score_field_for_source_id(
        "tzkhaar_fight_cave"
    ) == "midgame_boss_score"

    assert get_capability_score_field_for_source_id(
        "tzrek_jad"
    ) == "midgame_boss_score"

    assert get_capability_score_field_for_source_id(
        "tzek_jad"
    ) == "midgame_boss_score"

    assert get_capability_score_field_for_source_id(
        "wyrmscraig_goats"
    ) == "skilling_score"


def test_custom_clue_sources_map_to_clue_activity_score():
    assert get_capability_score_field_for_source_id(
        "clue_scrolls_medium_plus"
    ) == "clue_activity_score"
