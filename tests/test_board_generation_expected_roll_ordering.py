from decimal import Decimal

from utils.board_generation import (
    BoardSlot,
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
    ordered_slot_candidates,
)


def build_drop_candidate(title, expected_rolls=None):
    return TileCandidate(
        title=title,
        point_value=3,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.DROP,
                display_text=title,
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.TEAM_SUM,
                expected_rolls=expected_rolls,
            ),
        ),
    )


def test_required_drop_slot_orders_known_expected_rolls_first():
    slow = build_drop_candidate(
        "slow",
        Decimal("500"),
    )
    unknown = build_drop_candidate(
        "unknown",
    )
    fast = build_drop_candidate(
        "fast",
        Decimal("50"),
    )

    ordered_titles = [
        candidate.title
        for _, candidate in ordered_slot_candidates(
            BoardSlot(
                point_value=3,
                required_category=TileCategory.DROP,
            ),
            pending_slots=(),
            remaining_candidates=(
                slow,
                unknown,
                fast,
            ),
        )
    ]

    assert ordered_titles == [
        "fast",
        "slow",
        "unknown",
    ]


def test_required_drop_slot_preserves_input_order_for_equal_estimates():
    first = build_drop_candidate(
        "first",
        Decimal("50"),
    )
    second = build_drop_candidate(
        "second",
        Decimal("50"),
    )

    ordered_titles = [
        candidate.title
        for _, candidate in ordered_slot_candidates(
            BoardSlot(
                point_value=3,
                required_category=TileCategory.DROP,
            ),
            pending_slots=(),
            remaining_candidates=(
                first,
                second,
            ),
        )
    ]

    assert ordered_titles == [
        "first",
        "second",
    ]
