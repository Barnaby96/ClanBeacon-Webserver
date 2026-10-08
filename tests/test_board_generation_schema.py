import pytest

from utils.board_generation import (
    AccessConfidence,
    AccessFlag,
    AccessProfile,
    BoardAssemblyError,
    BoardGenerationRules,
    BoardSlot,
    ContributionMode,
    PetRole,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
    assemble_board_candidates,
    find_conflicting_tags,
    reserve_candidate_tags,
)


def test_secondary_pet_route_consumes_skill_pet_metric_and_source():
    candidate = TileCandidate(
        title="Gain 1,000,000 Thieving XP OR obtain Rocky",
        point_value=3,
        primary_category=TileCategory.SKILL,
        secondary_categories=frozenset(
            {
                TileCategory.PET
            }
        ),
        pet_role=PetRole.SECONDARY,
        route_mode=RouteMode.OR,
        routes=[
            Route(
                route_type=TileCategory.SKILL,
                display_text="Gain 1,000,000 Thieving XP",
                target=1_000_000,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="skill_thieving_xp",
                source_id="thieving",
                skill_id="thieving",
            ),
            Route(
                route_type=TileCategory.PET,
                display_text="Obtain Rocky",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.ANY_PLAYER,
                metric_id="pet_rocky",
                source_id="thieving",
                skill_id="thieving",
                pet_id="rocky",
            ),
        ],
        rng_level=4,
        has_fallback=True,
    )

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "skill:thieving",
            "metric:skill_thieving_xp",
            "metric:pet_rocky",
            "source:thieving",
            "pet:rocky",
        }
    )


def test_shared_source_conflicts_even_when_tile_category_differs():
    existing_tile = TileCandidate(
        title="Gain 1,000,000 Thieving XP",
        point_value=2,
        primary_category=TileCategory.SKILL,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.SKILL,
                display_text="Gain 1,000,000 Thieving XP",
                target=1_000_000,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="skill_thieving_xp",
                source_id="thieving",
                skill_id="thieving",
            )
        ],
    )

    used_tags = reserve_candidate_tags(
        existing_tile,
        frozenset()
    )

    rocky_tile = TileCandidate(
        title="Obtain Rocky",
        point_value=4,
        primary_category=TileCategory.PET,
        pet_role=PetRole.PRIMARY,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.PET,
                display_text="Obtain Rocky",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.ANY_PLAYER,
                metric_id="pet_rocky",
                source_id="thieving",
                skill_id="thieving",
                pet_id="rocky",
            )
        ],
        rng_level=4,
    )

    assert find_conflicting_tags(
        rocky_tile,
        used_tags
    ) == frozenset(
        {
            "source:thieving",
            "skill:thieving",
        }
    )


def test_non_overlapping_candidates_can_be_reserved():
    thieving_tile = TileCandidate(
        title="Gain 1,000,000 Thieving XP",
        point_value=2,
        primary_category=TileCategory.SKILL,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.SKILL,
                display_text="Gain 1,000,000 Thieving XP",
                target=1_000_000,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="skill_thieving_xp",
                source_id="thieving",
                skill_id="thieving",
            )
        ],
    )

    vorkath_tile = TileCandidate(
        title="Complete 150 Vorkath KC",
        point_value=3,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.KILLCOUNT,
                display_text="Complete 150 Vorkath KC",
                target=150,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="boss_vorkath_kc",
                source_id="vorkath",
                boss_id="vorkath",
            )
        ],
    )

    used_tags = reserve_candidate_tags(
        thieving_tile,
        frozenset()
    )
    used_tags = reserve_candidate_tags(
        vorkath_tile,
        used_tags
    )

    assert "skill:thieving" in used_tags
    assert "boss:vorkath" in used_tags


def test_single_route_mode_requires_exactly_one_route():
    with pytest.raises(
        ValueError,
        match="SINGLE route mode must contain exactly one route"
    ):
        TileCandidate(
            title="Bad single route tile",
            point_value=1,
            primary_category=TileCategory.HYBRID,
            route_mode=RouteMode.SINGLE,
            routes=[
                Route(
                    route_type=TileCategory.SKILL,
                    display_text="Gain Fishing XP",
                    target=100_000,
                    tracking_source=TrackingSource.WOM,
                    contribution_mode=ContributionMode.TEAM_SUM,
                    metric_id="skill_fishing_xp",
                    source_id="fishing",
                    skill_id="fishing",
                ),
                Route(
                    route_type=TileCategory.PET,
                    display_text="Obtain Heron",
                    target=1,
                    tracking_source=TrackingSource.DINK,
                    contribution_mode=ContributionMode.ANY_PLAYER,
                    metric_id="pet_heron",
                    source_id="fishing",
                    skill_id="fishing",
                    pet_id="heron",
                ),
            ],
        )


def test_n_of_route_mode_requires_valid_required_route_count():
    routes = [
        Route(
            route_type=TileCategory.SKILL,
            display_text="Gain Fishing XP",
            target=100_000,
            tracking_source=TrackingSource.WOM,
            contribution_mode=ContributionMode.TEAM_SUM,
            metric_id="skill_fishing_xp",
            source_id="fishing",
            skill_id="fishing",
        ),
        Route(
            route_type=TileCategory.KILLCOUNT,
            display_text="Complete Tempoross permits",
            target=10,
            tracking_source=TrackingSource.MANUAL,
            contribution_mode=ContributionMode.TEAM_SUM,
            metric_id="tempoross_permits",
            source_id="tempoross",
        ),
    ]

    with pytest.raises(
        ValueError,
        match="N_OF route mode requires required_route_count"
    ):
        TileCandidate(
            title="Bad N-of tile",
            point_value=2,
            primary_category=TileCategory.HYBRID,
            route_mode=RouteMode.N_OF,
            routes=routes,
        )

    candidate = TileCandidate(
        title="Good N-of tile",
        point_value=2,
        primary_category=TileCategory.HYBRID,
        route_mode=RouteMode.N_OF,
        routes=routes,
        required_route_count=1,
    )

    assert candidate.required_route_count == 1


def test_sum_route_mode_is_available():
    assert RouteMode.SUM.value == "SUM"


def make_schema_test_candidate(
    point_value=1,
    primary_category=TileCategory.SKILL,
    source_id="fishing",
    metric_id="skill_fishing_xp",
):
    return TileCandidate(
        title="Schema test tile",
        point_value=point_value,
        primary_category=primary_category,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=primary_category,
                display_text="Schema test route",
                target=100,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id=metric_id,
                source_id=source_id,
            )
        ],
    )


def test_default_board_generation_rules_build_twenty_five_slots():
    rules = BoardGenerationRules()

    slots = rules.build_slots()

    assert len(slots) == 25

    for point_value in range(1, 6):
        point_slots = [
            slot
            for slot in slots
            if slot.point_value == point_value
        ]

        assert len(point_slots) == 5

        required_categories = [
            slot.required_category
            for slot in point_slots
            if not slot.is_flex
        ]

        assert required_categories == [
            TileCategory.SKILL,
            TileCategory.KILLCOUNT,
            TileCategory.DROP,
        ]

        flex_slots = [
            slot
            for slot in point_slots
            if slot.is_flex
        ]

        assert len(flex_slots) == 2


def test_board_generation_rules_reject_invalid_distribution():
    with pytest.raises(
        ValueError,
        match="Points distribution must add up to board size"
    ):
        BoardGenerationRules(
            points_distribution={
                1: 5,
                2: 5,
                3: 5,
                4: 5,
                5: 4,
            }
        )


def test_board_generation_rules_reject_invalid_pet_limits():
    with pytest.raises(
        ValueError,
        match="Primary pet tile limits"
    ):
        BoardGenerationRules(
            primary_pet_tiles_min=3,
            primary_pet_tiles_target=2,
            primary_pet_tiles_max=2
        )


def test_board_slot_matches_candidate_by_point_and_category():
    skill_candidate = make_schema_test_candidate(
        point_value=2,
        primary_category=TileCategory.SKILL
    )

    assert BoardSlot(
        point_value=2,
        required_category=TileCategory.SKILL
    ).matches_candidate(skill_candidate)

    assert not BoardSlot(
        point_value=3,
        required_category=TileCategory.SKILL
    ).matches_candidate(skill_candidate)

    assert not BoardSlot(
        point_value=2,
        required_category=TileCategory.DROP
    ).matches_candidate(skill_candidate)

    assert BoardSlot(
        point_value=2
    ).matches_candidate(skill_candidate)


def make_assembly_candidate(
    point_value,
    primary_category,
    label,
    pet_role=PetRole.NONE,
    secondary_pet=False,
):
    base_source = f"{label}_source"
    base_metric = f"{label}_metric"

    if secondary_pet:
        return TileCandidate(
            title=f"{label} secondary pet tile",
            point_value=point_value,
            primary_category=primary_category,
            secondary_categories=frozenset(
                {
                    TileCategory.PET
                }
            ),
            pet_role=PetRole.SECONDARY,
            route_mode=RouteMode.OR,
            routes=[
                Route(
                    route_type=primary_category,
                    display_text=f"{label} main route",
                    target=100,
                    tracking_source=TrackingSource.WOM,
                    contribution_mode=ContributionMode.TEAM_SUM,
                    metric_id=base_metric,
                    source_id=base_source,
                ),
                Route(
                    route_type=TileCategory.PET,
                    display_text=f"{label} pet route",
                    target=1,
                    tracking_source=TrackingSource.DINK,
                    contribution_mode=ContributionMode.ANY_PLAYER,
                    metric_id=f"{label}_pet_metric",
                    source_id=base_source,
                    pet_id=f"{label}_pet",
                ),
            ],
            rng_level=4,
            has_fallback=True,
        )

    return TileCandidate(
        title=f"{label} tile",
        point_value=point_value,
        primary_category=primary_category,
        pet_role=pet_role,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=primary_category,
                display_text=f"{label} route",
                target=100,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id=base_metric,
                source_id=base_source,
                pet_id=(
                    f"{label}_pet"
                    if pet_role == PetRole.PRIMARY
                    else None
                ),
            )
        ],
        rng_level=(
            4
            if pet_role == PetRole.PRIMARY
            else 0
        ),
    )


def make_valid_assembly_candidate_pool():
    candidates = []

    for point_value in range(1, 6):
        candidates.extend(
            [
                make_assembly_candidate(
                    point_value,
                    TileCategory.SKILL,
                    f"p{point_value}_skill"
                ),
                make_assembly_candidate(
                    point_value,
                    TileCategory.KILLCOUNT,
                    f"p{point_value}_kc"
                ),
                make_assembly_candidate(
                    point_value,
                    TileCategory.DROP,
                    f"p{point_value}_drop"
                ),
            ]
        )

    candidates.extend(
        [
            make_assembly_candidate(
                1,
                TileCategory.PET,
                "primary_pet_one",
                pet_role=PetRole.PRIMARY
            ),
            make_assembly_candidate(
                1,
                TileCategory.HYBRID,
                "p1_hybrid"
            ),
            make_assembly_candidate(
                2,
                TileCategory.PET,
                "primary_pet_two",
                pet_role=PetRole.PRIMARY
            ),
            make_assembly_candidate(
                2,
                TileCategory.HYBRID,
                "p2_hybrid"
            ),
            make_assembly_candidate(
                3,
                TileCategory.HYBRID,
                "secondary_pet_one",
                pet_role=PetRole.SECONDARY,
                secondary_pet=True
            ),
            make_assembly_candidate(
                3,
                TileCategory.MANUAL,
                "p3_manual"
            ),
            make_assembly_candidate(
                4,
                TileCategory.HYBRID,
                "secondary_pet_two",
                pet_role=PetRole.SECONDARY,
                secondary_pet=True
            ),
            make_assembly_candidate(
                4,
                TileCategory.MANUAL,
                "p4_manual"
            ),
            make_assembly_candidate(
                5,
                TileCategory.HYBRID,
                "p5_hybrid"
            ),
            make_assembly_candidate(
                5,
                TileCategory.MANUAL,
                "p5_manual"
            ),
        ]
    )

    candidates.extend(
        [
            make_assembly_candidate(
                2,
                TileCategory.MANUAL,
                "p2_extra_flex"
            ),
            make_assembly_candidate(
                3,
                TileCategory.MANUAL,
                "p3_extra_flex"
            ),
            make_assembly_candidate(
                4,
                TileCategory.MANUAL,
                "p4_extra_flex"
            ),
            make_assembly_candidate(
                5,
                TileCategory.MANUAL,
                "p5_extra_flex"
            ),
        ]
    )

    return candidates


def test_assemble_board_candidates_fills_default_board_rules():
    board = assemble_board_candidates(
        make_valid_assembly_candidate_pool()
    )

    assert len(board.candidates) == 25
    assert board.point_total == 75

    assert sum(
        1
        for candidate in board.candidates
        if candidate.pet_role == PetRole.PRIMARY
    ) == 1

    assert sum(
        1
        for candidate in board.candidates
        if candidate.pet_role == PetRole.SECONDARY
    ) == 2


def test_assemble_board_candidates_skips_conflicting_candidate():
    rules = BoardGenerationRules(
        board_size=2,
        points_distribution={
            1: 2
        },
        required_categories_by_point={
            1: (
                TileCategory.SKILL,
                TileCategory.DROP,
            )
        },
        flex_slots_by_point={
            1: 0
        },
        primary_pet_tiles_min=0,
        primary_pet_tiles_target=0,
        primary_pet_tiles_max=0,
        secondary_pet_routes_min=0,
        secondary_pet_routes_target=0,
        secondary_pet_routes_max=0,
    )

    skill_tile = make_assembly_candidate(
        1,
        TileCategory.SKILL,
        "shared_source"
    )
    conflicting_drop = make_assembly_candidate(
        1,
        TileCategory.DROP,
        "shared_source"
    )
    valid_drop = make_assembly_candidate(
        1,
        TileCategory.DROP,
        "different_source"
    )

    board = assemble_board_candidates(
        [
            skill_tile,
            conflicting_drop,
            valid_drop,
        ],
        rules
    )

    assert board.candidates == (
        skill_tile,
        valid_drop,
    )


def test_assemble_board_candidates_raises_when_slot_cannot_be_filled():
    rules = BoardGenerationRules(
        board_size=2,
        points_distribution={
            1: 2
        },
        required_categories_by_point={
            1: (
                TileCategory.SKILL,
                TileCategory.DROP,
            )
        },
        flex_slots_by_point={
            1: 0
        },
        primary_pet_tiles_min=0,
        primary_pet_tiles_target=0,
        primary_pet_tiles_max=0,
        secondary_pet_routes_min=0,
        secondary_pet_routes_target=0,
        secondary_pet_routes_max=0,
    )

    with pytest.raises(
        BoardAssemblyError,
        match="Could not fill generated board"
    ):
        assemble_board_candidates(
            [
                make_assembly_candidate(
                    1,
                    TileCategory.SKILL,
                    "only_skill"
                )
            ],
            rules
        )


def test_assemble_board_candidates_respects_primary_pet_maximum():
    rules = BoardGenerationRules(
        board_size=2,
        points_distribution={
            1: 2
        },
        required_categories_by_point={
            1: ()
        },
        flex_slots_by_point={
            1: 2
        },
        primary_pet_tiles_min=0,
        primary_pet_tiles_target=1,
        primary_pet_tiles_max=1,
        secondary_pet_routes_min=0,
        secondary_pet_routes_target=0,
        secondary_pet_routes_max=0,
    )

    first_pet = make_assembly_candidate(
        1,
        TileCategory.PET,
        "first_pet",
        pet_role=PetRole.PRIMARY
    )
    second_pet = make_assembly_candidate(
        1,
        TileCategory.PET,
        "second_pet",
        pet_role=PetRole.PRIMARY
    )
    fallback = make_assembly_candidate(
        1,
        TileCategory.HYBRID,
        "fallback"
    )

    board = assemble_board_candidates(
        [
            first_pet,
            second_pet,
            fallback,
        ],
        rules
    )

    assert board.candidates == (
        first_pet,
        fallback,
    )


def test_access_profile_normalises_effective_and_recommended_skill_requirements():
    profile = AccessProfile(
        effective_skill_requirements={
            "Agility": 56,
            "Herblore": 10,
        },
        recommended_skill_requirements={
            "Ranged": 75,
            "Magic": 75,
        },
        access_flags=frozenset(
            {
                AccessFlag.QUEST_LOCKED
            }
        ),
        access_confidence=AccessConfidence.MEDIUM,
    )

    assert profile.effective_skill_requirements == {
        "agility": 56,
        "herblore": 10,
    }
    assert profile.recommended_skill_requirements == {
        "ranged": 75,
        "magic": 75,
    }
    assert profile.access_flags == frozenset(
        {
            AccessFlag.QUEST_LOCKED
        }
    )
    assert profile.access_confidence == AccessConfidence.MEDIUM


def test_access_profile_rejects_invalid_skill_levels():
    with pytest.raises(
        ValueError,
        match="Effective skill requirement for agility"
    ):
        AccessProfile(
            effective_skill_requirements={
                "Agility": 0
            }
        )

    with pytest.raises(
        ValueError,
        match="Recommended skill requirement for ranged"
    ):
        AccessProfile(
            recommended_skill_requirements={
                "Ranged": 120
            }
        )


def test_tile_candidate_can_store_access_profile_without_quest_names():
    profile = AccessProfile(
        effective_skill_requirements={
            "Agility": 56,
            "Crafting": 10,
            "Herblore": 10,
        },
        recommended_skill_requirements={
            "Ranged": 75,
            "Magic": 75,
        },
        access_flags=frozenset(
            {
                AccessFlag.QUEST_LOCKED
            }
        ),
        access_confidence=AccessConfidence.MEDIUM,
    )

    candidate = TileCandidate(
        title="Complete 150 Zulrah KC",
        point_value=3,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.KILLCOUNT,
                display_text="Complete 150 Zulrah KC",
                target=150,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id="boss_zulrah_kc",
                source_id="zulrah",
                boss_id="zulrah",
            )
        ],
        access_profile=profile,
    )

    assert candidate.access_profile.effective_skill_requirements == {
        "agility": 56,
        "crafting": 10,
        "herblore": 10,
    }
    assert AccessFlag.QUEST_LOCKED in candidate.access_profile.access_flags


def test_pet_group_route_consumes_pet_group_tag():
    candidate = TileCandidate(
        title="Obtain any skilling pet",
        point_value=4,
        primary_category=TileCategory.PET,
        pet_role=PetRole.PRIMARY,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.PET,
                display_text="Obtain any skilling pet",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.ANY_PLAYER,
                metric_id="pet_group_skilling_pets",
                source_id="skilling_pets",
                pet_group_id="skilling_pets",
            )
        ],
        rng_level=4,
    )

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "metric:pet_group_skilling_pets",
            "source:skilling_pets",
            "pet_group:skilling_pets",
        }
    )


def test_board_generation_rules_builds_required_slots_before_flex_slots():
    from utils.board_generation import BoardGenerationRules, TileCategory

    rules = BoardGenerationRules()
    slots = rules.build_slots()

    first_flex_index = next(
        index
        for index, slot in enumerate(slots)
        if slot.is_flex
    )

    assert all(
        not slot.is_flex
        for slot in slots[:first_flex_index]
    )
    assert all(
        slot.is_flex
        for slot in slots[first_flex_index:]
    )

    required_slots = slots[:first_flex_index]
    flex_slots = slots[first_flex_index:]

    assert len(required_slots) == 15
    assert len(flex_slots) == 10

    assert {
        slot.required_category
        for slot in required_slots
    } == {
        TileCategory.SKILL,
        TileCategory.KILLCOUNT,
        TileCategory.DROP,
    }


def test_assemble_board_candidates_accepts_candidate_order_key():
    rules = BoardGenerationRules(
        board_size=1,
        points_distribution={
            1: 1,
        },
        required_categories_by_point={
            1: (),
        },
        flex_slots_by_point={
            1: 1,
        },
        primary_pet_tiles_min=0,
        primary_pet_tiles_target=0,
        primary_pet_tiles_max=0,
        secondary_pet_routes_min=0,
        secondary_pet_routes_target=0,
        secondary_pet_routes_max=0,
    )

    normal_candidate = make_assembly_candidate(
        1,
        TileCategory.SKILL,
        "normal_candidate",
    )
    preferred_candidate = make_assembly_candidate(
        1,
        TileCategory.SKILL,
        "preferred_candidate",
    )

    board = assemble_board_candidates(
        [
            normal_candidate,
            preferred_candidate,
        ],
        rules,
        candidate_order_key=lambda candidate: (
            0
            if candidate is preferred_candidate
            else 1
        ),
    )

    assert board.candidates == (
        preferred_candidate,
    )


def test_default_board_generation_rules_cap_primary_pet_tiles_at_one():
    rules = BoardGenerationRules()

    assert rules.primary_pet_tiles_min == 1
    assert rules.primary_pet_tiles_target == 1
    assert rules.primary_pet_tiles_max == 1

def test_assemble_board_candidates_preserves_preselected_candidate():
    rules = BoardGenerationRules(
        board_size=2,
        points_distribution={
            1: 2,
        },
        required_categories_by_point={
            1: (
                TileCategory.SKILL,
            ),
        },
        flex_slots_by_point={
            1: 1,
        },
        primary_pet_tiles_min=0,
        primary_pet_tiles_target=0,
        primary_pet_tiles_max=0,
        secondary_pet_routes_min=0,
        secondary_pet_routes_target=0,
        secondary_pet_routes_max=0,
    )

    kept_candidate = make_assembly_candidate(
        1,
        TileCategory.SKILL,
        "kept",
    )
    filler_candidate = make_assembly_candidate(
        1,
        TileCategory.KILLCOUNT,
        "filler",
    )

    board = assemble_board_candidates(
        (
            kept_candidate,
            filler_candidate,
        ),
        rules=rules,
        preselected_candidates=(
            kept_candidate,
        ),
    )

    assert board.candidates[0] == kept_candidate
    assert board.candidates == (
        kept_candidate,
        filler_candidate,
    )


def test_assemble_board_candidates_rejects_conflicting_preselected_candidates():
    rules = BoardGenerationRules(
        board_size=2,
        points_distribution={
            1: 2,
        },
        required_categories_by_point={},
        flex_slots_by_point={
            1: 2,
        },
        primary_pet_tiles_min=0,
        primary_pet_tiles_target=0,
        primary_pet_tiles_max=0,
        secondary_pet_routes_min=0,
        secondary_pet_routes_target=0,
        secondary_pet_routes_max=0,
    )

    first_candidate = make_assembly_candidate(
        1,
        TileCategory.SKILL,
        "same_source",
    )
    second_candidate = make_assembly_candidate(
        1,
        TileCategory.SKILL,
        "same_source",
    )

    with pytest.raises(
        BoardAssemblyError,
        match="Preselected tile conflicts",
    ):
        assemble_board_candidates(
            (
                first_candidate,
                second_candidate,
            ),
            rules=rules,
            preselected_candidates=(
                first_candidate,
                second_candidate,
            ),
        )

