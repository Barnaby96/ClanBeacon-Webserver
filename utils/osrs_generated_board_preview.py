"""Helpers for previewing a generated OSRS Bingo board."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from utils.board_generation import BoardAssemblyError, assemble_board_candidates
from utils.osrs_tile_capability_assessment import (
    CAPABILITY_BALANCE_BALANCED,
    CAPABILITY_BALANCE_HIGH_GAP,
    CAPABILITY_BALANCE_MODERATE_GAP,
    CAPABILITY_BALANCE_NO_PROFILE_DATA,
    CAPABILITY_BALANCE_NO_SIGNAL,
    CAPABILITY_BALANCE_UNMAPPED,
    CAPABILITY_BALANCE_ZERO_SCORE_GAP,
    assess_candidate_capability,
)
from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates


CAPABILITY_GENERATION_BALANCE_BAND_ORDER = {
    CAPABILITY_BALANCE_BALANCED: 0,
    CAPABILITY_BALANCE_NO_SIGNAL: 1,
    CAPABILITY_BALANCE_NO_PROFILE_DATA: 2,
    CAPABILITY_BALANCE_UNMAPPED: 3,
    CAPABILITY_BALANCE_MODERATE_GAP: 4,
    CAPABILITY_BALANCE_HIGH_GAP: 5,
    CAPABILITY_BALANCE_ZERO_SCORE_GAP: 6,
}


def build_capability_candidate_order_key(capability_profiles):
    def candidate_order_key(candidate):
        assessment = assess_candidate_capability(
            candidate,
            capability_profiles,
        )

        return (
            CAPABILITY_GENERATION_BALANCE_BAND_ORDER.get(
                assessment.balance_band,
                99,
            ),
            assessment.zero_score_profile_count,
            assessment.score_gap or 0,
            -(
                assessment.minimum_score
                or 0
            ),
        )

    return candidate_order_key


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
    capability_ordering_applied: bool = False
    capability_ordering_fell_back: bool = False
    capability_ordering_fallback_reason: str | None = None


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
    capability_ordering_applied=False,
    capability_ordering_fell_back=False,
    capability_ordering_fallback_reason=None,
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
        capability_ordering_applied=capability_ordering_applied,
        capability_ordering_fell_back=capability_ordering_fell_back,
        capability_ordering_fallback_reason=capability_ordering_fallback_reason,
    )


def get_curated_generated_board_preview_summary(
    capability_profiles=None,
):
    candidate_order_key = None
    capability_ordering_applied = False
    capability_ordering_fell_back = False
    capability_ordering_fallback_reason = None

    if capability_profiles is not None:
        candidate_order_key = build_capability_candidate_order_key(
            capability_profiles
        )
        capability_ordering_applied = True

    generation_candidates = get_curated_tile_generation_candidates()

    try:
        board = assemble_board_candidates(
            generation_candidates,
            candidate_order_key=candidate_order_key,
        )
    except BoardAssemblyError as error:
        if candidate_order_key is None:
            raise

        capability_ordering_fell_back = True
        capability_ordering_fallback_reason = str(error)

        board = assemble_board_candidates(
            generation_candidates,
        )

    return build_generated_board_preview_summary(
        board,
        capability_profiles=capability_profiles,
        capability_ordering_applied=capability_ordering_applied,
        capability_ordering_fell_back=capability_ordering_fell_back,
        capability_ordering_fallback_reason=capability_ordering_fallback_reason,
    )
