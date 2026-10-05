"""Helpers for previewing a generated OSRS Bingo board."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from utils.board_generation import assemble_board_candidates
from utils.osrs_tile_capability_assessment import assess_candidate_capability
from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates


@dataclass(frozen=True)
class GeneratedBoardPreviewRow:
    point_value: int
    category: str
    title: str
    hard_unique_tags: tuple
    route_descriptions: tuple
    capability_score_field: str | None = None
    capability_score_field_label: str | None = None
    capability_balance_band: str | None = None
    capability_warning_level: str | None = None
    capability_summary_text: str | None = None


@dataclass(frozen=True)
class GeneratedBoardPreviewSummary:
    candidate_count: int
    counts_by_point_value: dict
    counts_by_primary_category: dict
    rows_by_point_value: dict


def build_generated_board_preview_row(
    candidate,
    capability_profiles=None,
):
    capability_assessment = None

    if capability_profiles is not None:
        capability_assessment = assess_candidate_capability(
            candidate,
            capability_profiles,
        )

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
        capability_score_field=(
            capability_assessment.capability_score_field
            if capability_assessment is not None
            else None
        ),
        capability_score_field_label=(
            capability_assessment.score_field_label
            if capability_assessment is not None
            else None
        ),
        capability_balance_band=(
            capability_assessment.balance_band
            if capability_assessment is not None
            else None
        ),
        capability_warning_level=(
            capability_assessment.warning_level
            if capability_assessment is not None
            else None
        ),
        capability_summary_text=(
            capability_assessment.summary_text
            if capability_assessment is not None
            else None
        ),
    )


def build_generated_board_preview_summary(
    board,
    capability_profiles=None,
):
    rows = [
        build_generated_board_preview_row(
            candidate,
            capability_profiles=capability_profiles,
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


def get_curated_generated_board_preview_summary(
    capability_profiles=None,
):
    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    return build_generated_board_preview_summary(
        board,
        capability_profiles=capability_profiles,
    )
