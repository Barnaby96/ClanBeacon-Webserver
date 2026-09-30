import pytest

from utils.board_generation import (
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
)
from utils.osrs_generation_recipes import (
    StaticPointTargetModel,
    build_single_tile_candidate,
)
from utils.osrs_tile_candidate_validation import (
    assert_valid_tile_candidate,
    assert_valid_tile_candidate_pool,
    route_condition_signature,
    validate_tile_candidate,
    validate_tile_candidate_pool,
)
from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)


def make_callisto_route(target=35):
    return Route(
        route_type=TileCategory.KILLCOUNT,
        display_text=f"Complete {target} Callisto KC",
        target=target,
        tracking_source=TrackingSource.WOM,
        contribution_mode=ContributionMode.TEAM_SUM,
        metric_id="boss_callisto_kc",
        source_id="callisto",
        boss_id="callisto",
    )


def test_route_condition_signature_normalises_route_identity():
    route = make_callisto_route()

    assert route_condition_signature(
        route
    ) == (
        "KILLCOUNT",
        "boss_callisto_kc",
        "callisto",
        None,
        "callisto",
        None,
        None,
        None,
        None,
    )


def test_validate_tile_candidate_accepts_component_single_candidate():
    component = TileComponent(
        component_id="Callisto KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Callisto",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Callisto",
        boss_id="Callisto",
    )
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            3: 35,
        },
    )
    candidate = build_single_tile_candidate(
        component,
        3,
        target_model,
    )

    assert validate_tile_candidate(
        candidate
    ) == ()
    assert assert_valid_tile_candidate(
        candidate
    ) is candidate


def test_validate_tile_candidate_rejects_non_positive_route_target():
    route = make_callisto_route(
        target=0
    )
    candidate = TileCandidate(
        title="Bad Callisto target",
        point_value=1,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=RouteMode.SINGLE,
        routes=(
            route,
        ),
    )

    assert validate_tile_candidate(
        candidate
    ) == (
        "Route 1 target must be positive.",
    )


def test_validate_tile_candidate_rejects_duplicate_route_conditions():
    route = make_callisto_route()
    candidate = TileCandidate(
        title="Duplicate Callisto routes",
        point_value=3,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=RouteMode.OR,
        routes=(
            route,
            route,
        ),
    )

    assert validate_tile_candidate(
        candidate
    ) == (
        "Candidate contains duplicate route conditions.",
    )


def test_validate_tile_candidate_pool_reports_candidate_title():
    route = make_callisto_route(
        target=0
    )
    candidate = TileCandidate(
        title="Bad target",
        point_value=1,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=RouteMode.SINGLE,
        routes=(
            route,
        ),
    )

    issues = validate_tile_candidate_pool(
        (
            candidate,
        )
    )

    assert len(
        issues
    ) == 1
    assert issues[0].candidate_title == "Bad target"
    assert issues[0].message == "Route 1 target must be positive."

    with pytest.raises(
        ValueError,
        match="Bad target: Route 1 target must be positive",
    ):
        assert_valid_tile_candidate_pool(
            (
                candidate,
            )
        )


def test_curated_generation_candidates_pass_common_validation():
    candidates = get_curated_tile_generation_candidates()

    assert validate_tile_candidate_pool(
        candidates
    ) == ()
    assert_valid_tile_candidate_pool(
        candidates
    )
