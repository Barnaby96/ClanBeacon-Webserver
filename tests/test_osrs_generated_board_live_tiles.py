from utils.board_generation import (
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
)
from utils.osrs_generated_board_live_tiles import (
    build_live_tile_payload_from_candidate,
    build_live_tile_payloads_from_generated_board_keys,
)
from utils.osrs_tile_catalogue import (
    get_curated_tile_generation_candidates,
)
from utils.osrs_generated_board_preview import (
    build_generated_board_candidate_key,
    get_curated_generated_board_preview_summary,
)


def test_build_live_tile_payload_for_single_skill_route():
    candidate = TileCandidate(
        title="Gain 1,000,000 Thieving XP",
        point_value=3,
        primary_category=TileCategory.SKILL,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.SKILL,
                display_text="Gain 1,000,000 Thieving XP",
                target=1_000_000,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="thieving",
                skill_id="thieving",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload == {
        "tile_name": "Gain 1,000,000 Thieving XP",
        "tile_points": 3,
        "tile_rules": "Gain 1,000,000 Thieving XP",
        "conditions": [
            {
                "completion_path": 1,
                "condition_type": "EXPERIENCE",
                "condition_trigger": "thieving",
                "target": 1_000_000,
            },
        ],
        "completion_paths": [
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None,
                "require_unique": False,
            },
        ],
    }


def test_build_live_skill_routes_use_exact_wom_metrics():
    cases = (
        (
            "Runecraft",
            "runecraft",
            "runecrafting",
        ),
        (
            "Sailing",
            "sailing",
            "sailing",
        ),
    )

    for skill_name, skill_id, wom_metric in cases:
        candidate = TileCandidate(
            title=f"Gain 250,000 {skill_name} XP",
            point_value=1,
            primary_category=TileCategory.SKILL,
            route_mode=RouteMode.SINGLE,
            routes=(
                Route(
                    route_type=TileCategory.SKILL,
                    display_text=(
                        f"Gain 250,000 {skill_name} XP"
                    ),
                    target=250_000,
                    tracking_source=TrackingSource.WOM,
                    contribution_mode=ContributionMode.TEAM_SUM,
                    metric_id=wom_metric,
                    skill_id=skill_id,
                ),
            ),
        )

        payload = build_live_tile_payload_from_candidate(
            candidate
        )

        assert payload["conditions"][0][
            "condition_trigger"
        ] == wom_metric


def test_build_live_tile_payload_for_skill_or_pet_routes():
    candidate = TileCandidate(
        title="Gain 1,000,000 Thieving XP OR obtain Rocky",
        point_value=4,
        primary_category=TileCategory.SKILL,
        secondary_categories=frozenset(
            {
                TileCategory.PET,
            }
        ),
        route_mode=RouteMode.OR,
        routes=(
            Route(
                route_type=TileCategory.SKILL,
                display_text="Gain 1,000,000 Thieving XP",
                target=1_000_000,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="thieving",
                skill_id="thieving",
            ),
            Route(
                route_type=TileCategory.PET,
                display_text="Obtain Rocky",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.ANY_PLAYER,
                metric_id="pet_rocky",
                skill_id="thieving",
                pet_id="rocky",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload == {
        "tile_name": "Gain 1,000,000 Thieving XP OR obtain Rocky",
        "tile_points": 4,
        "tile_rules": (
            "Gain 1,000,000 Thieving XP OR Obtain Rocky"
        ),
        "conditions": [
            {
                "completion_path": 1,
                "condition_type": "EXPERIENCE",
                "condition_trigger": "thieving",
                "target": 1_000_000,
            },
            {
                "completion_path": 2,
                "condition_type": "PET",
                "condition_trigger": "Rocky",
                "target": 1,
            },
        ],
        "completion_paths": [
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None,
                "require_unique": False,
            },
            {
                "completion_path": 2,
                "route_mode": "ALL",
                "route_target": None,
                "require_unique": False,
            },
        ],
    }


def test_build_live_tile_payload_for_n_of_metric_routes():
    candidate = TileCandidate(
        title="Skilling minigame sampler",
        point_value=3,
        primary_category=TileCategory.HYBRID,
        route_mode=RouteMode.N_OF,
        required_route_count=2,
        routes=(
            Route(
                route_type=TileCategory.HYBRID,
                display_text=(
                    "Complete 100 Guardians of the Rift completions"
                ),
                target=100,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="guardians_of_the_rift",
            ),
            Route(
                route_type=TileCategory.HYBRID,
                display_text="Complete 100 Tempoross completions",
                target=100,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="tempoross",
            ),
            Route(
                route_type=TileCategory.HYBRID,
                display_text="Complete 100 Wintertodt kills",
                target=100,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="wintertodt",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload == {
        "tile_name": "Skilling minigame sampler",
        "tile_points": 3,
        "tile_rules": (
            "Complete 2 of: "
            "Complete 100 Guardians of the Rift completions; "
            "Complete 100 Tempoross completions; "
            "Complete 100 Wintertodt kills"
        ),
        "conditions": [
            {
                "completion_path": 1,
                "condition_type": "METRIC",
                "condition_trigger": (
                    "guardians_of_the_rift"
                ),
                "target": 100,
            },
            {
                "completion_path": 1,
                "condition_type": "METRIC",
                "condition_trigger": "tempoross",
                "target": 100,
            },
            {
                "completion_path": 1,
                "condition_type": "METRIC",
                "condition_trigger": "wintertodt",
                "target": 100,
            },
        ],
        "completion_paths": [
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 2,
                "require_unique": False,
            },
        ],
    }


def test_build_live_tile_payload_for_sum_metric_routes():
    candidate = TileCandidate(
        title="Complete 10 medium-or-harder clue scrolls",
        point_value=1,
        primary_category=TileCategory.HYBRID,
        route_mode=RouteMode.SUM,
        routes=(
            Route(
                route_type=TileCategory.HYBRID,
                display_text="clue_scrolls_medium",
                target=10,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="clue_scrolls_medium",
            ),
            Route(
                route_type=TileCategory.HYBRID,
                display_text="clue_scrolls_hard",
                target=10,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="clue_scrolls_hard",
            ),
            Route(
                route_type=TileCategory.HYBRID,
                display_text="clue_scrolls_elite",
                target=10,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="clue_scrolls_elite",
            ),
            Route(
                route_type=TileCategory.HYBRID,
                display_text="clue_scrolls_master",
                target=10,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="clue_scrolls_master",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(
        candidate
    )

    assert payload["conditions"] == [
        {
            "completion_path": 1,
            "condition_type": "METRIC",
            "condition_trigger": "clue_scrolls_medium",
            "target": 10,
        },
        {
            "completion_path": 1,
            "condition_type": "METRIC",
            "condition_trigger": "clue_scrolls_hard",
            "target": 10,
        },
        {
            "completion_path": 1,
            "condition_type": "METRIC",
            "condition_trigger": "clue_scrolls_elite",
            "target": 10,
        },
        {
            "completion_path": 1,
            "condition_type": "METRIC",
            "condition_trigger": "clue_scrolls_master",
            "target": 10,
        },
    ]

    assert payload["completion_paths"] == [
        {
            "completion_path": 1,
            "route_mode": "SUM",
            "route_target": 10,
            "require_unique": False,
        },
    ]


def test_build_live_tile_payload_for_drop_group_route():
    candidate = TileCandidate(
        title="Obtain 1 Abyssal Bludgeon Part",
        point_value=2,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.DROP,
                display_text="Obtain 1 Abyssal Bludgeon Part",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.N_OF_UNIQUES,
                drop_group_id="abyssal_bludgeon_part",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload == {
        "tile_name": "Obtain 1 Abyssal Bludgeon Part",
        "tile_points": 2,
        "tile_rules": "Obtain 1 Abyssal Bludgeon Part",
        "conditions": [
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Bludgeon axon",
                "target": 1,
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Bludgeon claw",
                "target": 1,
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Bludgeon spine",
                "target": 1,
            },
        ],
        "completion_paths": [
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 1,
                "require_unique": True,
            },
        ],
    }


def test_build_live_tile_payload_for_repeatable_vorkath_drop_group():
    candidate = TileCandidate(
        title="Obtain 2 Vorkath unique drops (duplicates allowed)",
        point_value=4,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.DROP,
                display_text="Obtain 2 Vorkath unique drops (duplicates allowed)",
                target=2,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.TEAM_SUM,
                drop_group_id="vorkath_uniques",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload["completion_paths"] == [
        {
            "completion_path": 1,
            "route_mode": "N_OF",
            "route_target": 2,
            "require_unique": False,
        },
    ]

    assert {
        condition["condition_trigger"]
        for condition in payload["conditions"]
    } == {
        "Skeletal visage",
        "Dragonbone necklace",
        "Jar of decay",
    }

    assert all(
        condition["target"] == 2
        for condition in payload["conditions"]
    )


def test_existing_generated_vorkath_group_remains_distinct():
    from utils.osrs_tile_catalogue import (
        get_curated_tile_generation_candidates,
    )

    candidate = next(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if candidate.title == "Obtain 2 Vorkath Uniques"
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload["completion_paths"] == [
        {
            "completion_path": 1,
            "route_mode": "N_OF",
            "route_target": 2,
            "require_unique": True,
        },
    ]

    assert all(
        condition["target"] == 1
        for condition in payload["conditions"]
    )


def test_build_live_tile_payload_for_specific_drop_route():
    candidate = TileCandidate(
        title="Obtain Bludgeon axon",
        point_value=2,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.DROP,
                display_text="Obtain Bludgeon axon",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.TEAM_SUM,
                drop_id="bludgeon_axon",
                drop_group_id="abyssal_bludgeon_part",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload == {
        "tile_name": "Obtain Bludgeon axon",
        "tile_points": 2,
        "tile_rules": "Obtain Bludgeon axon",
        "conditions": [
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Bludgeon axon",
                "target": 1,
            },
        ],
        "completion_paths": [
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None,
                "require_unique": False,
            },
        ],
    }


def test_build_live_tile_payload_for_killcount_route():
    candidate = TileCandidate(
        title="Complete 50 Zulrah KC",
        point_value=2,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.KILLCOUNT,
                display_text="Complete 50 Zulrah KC",
                target=50,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="boss_zulrah_kc",
                boss_id="zulrah",
            ),
        ),
    )

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload == {
        "tile_name": "Complete 50 Zulrah KC",
        "tile_points": 2,
        "tile_rules": "Complete 50 Zulrah KC",
        "conditions": [
            {
                "completion_path": 1,
                "condition_type": "KILLCOUNT",
                "condition_trigger": "zulrah",
                "target": 50,
            },
        ],
        "completion_paths": [
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None,
                "require_unique": False,
            },
        ],
    }


def test_all_curated_candidates_convert_to_live_tile_payloads():
    candidates = get_curated_tile_generation_candidates()

    assert len(candidates) == 690

    for candidate in candidates:
        payload = build_live_tile_payload_from_candidate(
            candidate
        )

        assert payload["tile_name"] == candidate.title
        assert payload["tile_points"] == candidate.point_value
        assert payload["tile_rules"]
        assert payload["conditions"]
        assert payload["completion_paths"]



def test_build_live_tile_payloads_from_exact_generated_board_keys():
    summary = get_curated_generated_board_preview_summary()

    tile_keys = tuple(
        row.tile_key
        for point_value in sorted(
            summary.rows_by_point_value
        )
        for row in summary.rows_by_point_value[
            point_value
        ]
    )

    assert len(tile_keys) == 25

    payloads = (
        build_live_tile_payloads_from_generated_board_keys(
            tile_keys
        )
    )

    assert len(payloads) == 25

    candidate_by_key = {
        build_generated_board_candidate_key(
            candidate
        ): candidate
        for candidate in get_curated_tile_generation_candidates()
    }

    expected_candidates = [
        candidate_by_key[tile_key]
        for tile_key in tile_keys
    ]

    assert [
        payload["tile_name"]
        for payload in payloads
    ] == [
        candidate.title
        for candidate in expected_candidates
    ]

    assert [
        payload["tile_points"]
        for payload in payloads
    ] == [
        candidate.point_value
        for candidate in expected_candidates
    ]


def test_vorki_or_vorkath_unique_group_live_conversion():
    from dataclasses import replace

    from utils.board_generation import (
        PetRole,
        RouteMode,
        TileCategory,
    )
    from utils.osrs_tile_catalogue import (
        get_curated_tile_generation_candidates,
    )

    catalogue = get_curated_tile_generation_candidates()

    unique_candidate = next(
        candidate
        for candidate in catalogue
        if candidate.title == "Obtain 1 Vorkath Unique"
    )

    pet_candidate = next(
        candidate
        for candidate in catalogue
        if candidate.title == "Obtain Vorki"
    )

    assert (
        unique_candidate.access_profile
        == pet_candidate.access_profile
    )

    candidate = replace(
        unique_candidate,
        title="Obtain 1 Vorkath Unique OR obtain Vorki",
        route_mode=RouteMode.OR,
        routes=(
            unique_candidate.routes[0],
            pet_candidate.routes[0],
        ),
        primary_category=TileCategory.DROP,
        secondary_categories=frozenset({
            TileCategory.PET,
        }),
        pet_role=PetRole.SECONDARY,
        rng_level=max(
            unique_candidate.rng_level,
            pet_candidate.rng_level,
        ),
    )

    assert "source:vorkath" in candidate.all_hard_unique_tags

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload["completion_paths"] == [
        {
            "completion_path": 1,
            "route_mode": "N_OF",
            "route_target": 1,
            "require_unique": True,
        },
        {
            "completion_path": 2,
            "route_mode": "ALL",
            "route_target": None,
            "require_unique": False,
        },
    ]

    assert {
        (
            condition["completion_path"],
            condition["condition_type"],
            condition["condition_trigger"],
            condition["target"],
        )
        for condition in payload["conditions"]
    } == {
        (1, "DROP", "Skeletal visage", 1),
        (1, "DROP", "Dragonbone necklace", 1),
        (1, "DROP", "Jar of decay", 1),
        (2, "PET", "Vorki", 1),
    }
