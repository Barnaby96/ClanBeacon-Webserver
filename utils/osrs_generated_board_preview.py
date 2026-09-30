"""Helpers for previewing a generated OSRS Bingo board."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from utils.board_generation import assemble_board_candidates
from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates


@dataclass(frozen=True)
class GeneratedBoardPreviewRow:
    point_value: int
    category: str
    title: str
    hard_unique_tags: tuple
    route_descriptions: tuple


@dataclass(frozen=True)
class GeneratedBoardPreviewSummary:
    candidate_count: int
    counts_by_point_value: dict
    counts_by_primary_category: dict
    rows_by_point_value: dict


def build_generated_board_preview_row(candidate):
    return GeneratedBoardPreviewRow(
        point_value=candidate.point_value,
        category=candidate.primary_category.value,
        title=candidate.title,
        hard_unique_tags=tuple(
            sorted(
                candidate.all_hard_unique_tags
            )
        ),
        route_descriptions=tuple(
            route.display_text
            for route in candidate.routes
        ),
    )


def build_generated_board_preview_summary(board):
    rows = [
        build_generated_board_preview_row(
            candidate
        )
        for candidate in board.candidates
    ]

    rows_by_point_value = defaultdict(
        list
    )

    for row in rows:
        rows_by_point_value[row.point_value].append(
            row
        )

    return GeneratedBoardPreviewSummary(
        candidate_count=len(rows),
        counts_by_point_value=dict(
            sorted(
                Counter(
                    row.point_value
                    for row in rows
                ).items()
            )
        ),
        counts_by_primary_category=dict(
            sorted(
                Counter(
                    row.category
                    for row in rows
                ).items()
            )
        ),
        rows_by_point_value={
            point_value: tuple(point_rows)
            for point_value, point_rows in sorted(
                rows_by_point_value.items()
            )
        },
    )


def get_curated_generated_board_preview_summary():
    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    return build_generated_board_preview_summary(
        board
    )
