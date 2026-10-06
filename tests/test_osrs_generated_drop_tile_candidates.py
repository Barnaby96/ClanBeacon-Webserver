from decimal import Decimal

from utils.board_generation import TileCategory
from utils.osrs_drop_tile_effort import (
    DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
    DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
)
from utils.osrs_drop_tile_effort_preview import DropTileEffortPreviewRow
from utils.osrs_generated_drop_tile_candidates import (
    build_generated_drop_tile_candidate,
    build_generated_drop_tile_candidates,
)


def make_row(**overrides):
    values = {
        "tile_mode": DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
        "drop_group_id": "zulrah_unique",
        "display_name": "Zulrah uniques",
        "source_id": "zulrah",
        "source_name": "Zulrah",
        "target": 1,
        "drop_id": None,
        "drop_name": None,
        "drop_rate": None,
        "expected_rolls": Decimal("128"),
        "total_effort": Decimal("192"),
        "suggested_point_value": 2,
        "raw_suggested_point_value": 2,
        "minimum_point_value": None,
        "parseable": True,
        "reason": "Estimated from group drop rates.",
        "access_requirement_multiplier": Decimal("1.25"),
        "source_difficulty_multiplier": Decimal("1.5"),
        "source_effort_reason": "Requires access and boss completion.",
    }
    values.update(overrides)
    return DropTileEffortPreviewRow(**values)


def test_build_generated_group_drop_tile_candidate():
    candidate = build_generated_drop_tile_candidate(
        make_row()
    )

    route = candidate.routes[0]

    assert candidate.title == "Obtain 1 Zulrah uniques"
    assert candidate.point_value == 2
    assert candidate.primary_category == TileCategory.DROP
    assert route.drop_group_id == "zulrah_unique"
    assert route.drop_id is None
    assert route.target == 1
    assert route.expected_rolls == Decimal("128")


def test_build_generated_specific_drop_tile_candidate():
    candidate = build_generated_drop_tile_candidate(
        make_row(
            tile_mode=DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
            drop_id="tanzanite_fang",
            drop_name="Tanzanite fang",
            target=None,
            expected_rolls=Decimal("512"),
            suggested_point_value=4,
            raw_suggested_point_value=4,
        )
    )

    route = candidate.routes[0]

    assert candidate.title == "Obtain Tanzanite fang"
    assert candidate.point_value == 4
    assert route.drop_group_id == "zulrah_unique"
    assert route.drop_id == "tanzanite_fang"
    assert route.target == 1
    assert route.expected_rolls == Decimal("512")


def test_build_generated_drop_tile_candidates_filters_unsupported_rows():
    valid = make_row()
    unparseable = make_row(parseable=False)
    missing_points = make_row(suggested_point_value=None)

    candidates = build_generated_drop_tile_candidates(
        rows=(
            valid,
            unparseable,
            missing_points,
        )
    )

    assert len(candidates) == 1
    assert candidates[0].title == "Obtain 1 Zulrah uniques"



def test_build_generated_group_drop_tile_candidate_singularises_uniques():
    candidate = build_generated_drop_tile_candidate(
        make_row(
            display_name="Phantom Muspah Uniques",
            target=1,
        )
    )

    assert candidate.title == "Obtain 1 Phantom Muspah Unique"
    assert candidate.routes[0].display_text == "Obtain 1 Phantom Muspah Unique"
