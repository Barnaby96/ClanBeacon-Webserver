def test_vorki_or_vorkath_kc_uses_secondary_pet_and_independent_paths():
    from utils.board_generation import (
        PetRole,
        RouteMode,
        TileCategory,
    )
    from utils.osrs_generated_board_live_tiles import (
        build_live_tile_payload_from_candidate,
    )
    from utils.osrs_vorkath_recipes import (
        build_vorkath_pet_or_kc_candidate,
    )

    # Fixture only: this point tier is not an approved calibration.
    candidate = build_vorkath_pet_or_kc_candidate(
        kc_target=150,
        point_value=3,
    )

    assert candidate.point_value == 3
    assert candidate.primary_category == TileCategory.KILLCOUNT
    assert candidate.secondary_categories == frozenset({
        TileCategory.PET,
    })
    assert candidate.pet_role == PetRole.SECONDARY
    assert candidate.route_mode == RouteMode.OR
    assert len(candidate.routes) == 2

    kc_route, pet_route = candidate.routes

    assert kc_route.route_type == TileCategory.KILLCOUNT
    assert kc_route.boss_id == "vorkath"
    assert kc_route.target == 150

    assert pet_route.route_type == TileCategory.PET
    assert pet_route.pet_id == "vorki"
    assert pet_route.target == 1

    assert {
        "source:vorkath",
        "boss:vorkath",
        "pet:vorki",
    }.issubset(candidate.all_hard_unique_tags)

    payload = build_live_tile_payload_from_candidate(candidate)

    assert payload["completion_paths"] == [
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
    ]

    assert len(payload["conditions"]) == 2
    assert payload["conditions"][0]["target"] == 150
    assert payload["conditions"][1] == {
        "completion_path": 2,
        "condition_type": "PET",
        "condition_trigger": "Vorki",
        "target": 1,
    }


def test_vorki_or_vorkath_unique_uses_secondary_pet_and_group_path():
    from utils.board_generation import (
        PetRole,
        RouteMode,
        TileCategory,
    )
    from utils.osrs_generated_board_live_tiles import (
        build_live_tile_payload_from_candidate,
    )
    from utils.osrs_vorkath_recipes import (
        build_vorkath_pet_or_unique_candidate,
    )

    # Fixture only; difficulty calibration remains outstanding.
    candidate = build_vorkath_pet_or_unique_candidate(
        distinct_drop_target=1,
        point_value=4,
    )

    assert candidate.primary_category == TileCategory.DROP
    assert candidate.secondary_categories == frozenset({
        TileCategory.PET,
    })
    assert candidate.pet_role == PetRole.SECONDARY
    assert candidate.route_mode == RouteMode.OR
    assert candidate.point_value == 4
    assert len(candidate.routes) == 2

    drop_route, pet_route = candidate.routes

    assert drop_route.route_type == TileCategory.DROP
    assert drop_route.drop_group_id == "vorkath_uniques"
    assert drop_route.target == 1

    assert pet_route.route_type == TileCategory.PET
    assert pet_route.pet_id == "vorki"
    assert pet_route.target == 1

    assert {
        "source:vorkath",
        "drop_group:vorkath_uniques",
        "pet:vorki",
    }.issubset(candidate.all_hard_unique_tags)

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
