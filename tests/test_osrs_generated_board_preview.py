from utils.osrs_generated_board_preview import (
    build_generated_board_preview_summary,
    get_curated_generated_board_preview_summary,
)
from utils.board_generation import assemble_board_candidates
from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates


def test_build_generated_board_preview_summary_groups_rows_by_point_value():
    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    summary = build_generated_board_preview_summary(
        board
    )

    assert summary.candidate_count == 25
    assert summary.counts_by_point_value == {
        1: 5,
        2: 5,
        3: 5,
        4: 5,
        5: 5,
    }
    assert set(summary.rows_by_point_value) == {
        1,
        2,
        3,
        4,
        5,
    }
    assert all(
        len(rows) == 5
        for rows in summary.rows_by_point_value.values()
    )


def test_curated_generated_board_preview_summary_includes_tags_and_routes():
    summary = get_curated_generated_board_preview_summary()

    rows = [
        row
        for point_rows in summary.rows_by_point_value.values()
        for row in point_rows
    ]

    assert len(rows) == 25
    assert all(
        row.title
        for row in rows
    )
    assert all(
        row.route_descriptions
        for row in rows
    )
    assert any(
        "source:zulrah" in row.hard_unique_tags
        for row in rows
    )
