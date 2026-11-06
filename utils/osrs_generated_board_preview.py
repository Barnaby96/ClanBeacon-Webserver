"""Helpers for previewing a generated OSRS Bingo board."""

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json

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

def build_generated_board_candidate_key(candidate):
    payload = {
        "point_value": candidate.point_value,
        "primary_category": (
            candidate.primary_category.value
            if candidate.primary_category is not None
            else None
        ),
        "title": candidate.title,
        "routes": [
            {
                "route_type": route.route_type.value,
                "display_text": route.display_text,
                "target": route.target,
                "source_id": route.source_id,
                "metric_id": route.metric_id,
                "skill_id": route.skill_id,
                "boss_id": route.boss_id,
                "drop_id": route.drop_id,
                "drop_group_id": route.drop_group_id,
                "pet_id": route.pet_id,
            }
            for route in candidate.routes
        ],
        "hard_unique_tags": sorted(
            candidate.all_hard_unique_tags
        ),
    }

    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()

@dataclass(frozen=True)
class GeneratedBoardPreviewRow:
    tile_key: str
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
        tile_key=build_generated_board_candidate_key(candidate),
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


def get_candidate_by_generated_board_key(candidates):
    return {
        build_generated_board_candidate_key(candidate): candidate
        for candidate in candidates
    }


def build_candidate_access_by_team(
    candidates,
    *,
    capability_result,
    participating_team_names,
    route_access_profiles_by_candidate,
):
    """Build per-team access assessments for candidate filtering.

    Reuses rostered WOM evidence and the existing team-level
    route evaluator. Does not fetch additional player data.

    Missing route metadata stays unknown. DROP routes remain
    unapproved until verified acquisition-source assessment
    is connected separately.
    """
    from collections.abc import Mapping

    from utils.osrs_player_access import (
        assess_team_candidate_route_access,
    )

    if not isinstance(
        participating_team_names,
        (tuple, list),
    ):
        return {}

    team_names = tuple(participating_team_names)

    # An empty or invalid participating-team list cannot
    # establish access for the board.
    if not team_names:
        return {}

    if any(
        not isinstance(name, str)
        or not name
        or name != name.strip()
        for name in team_names
    ):
        return {}

    if len(set(team_names)) != len(team_names):
        return {}

    if not isinstance(
        route_access_profiles_by_candidate,
        Mapping,
    ):
        route_access_profiles_by_candidate = {}

    candidate_entries = []
    seen_candidate_keys = set()

    for candidate in candidates:
        candidate_key = build_generated_board_candidate_key(
            candidate
        )

        # Refuse ambiguous duplicate candidate identities.
        if candidate_key in seen_candidate_keys:
            return {}

        seen_candidate_keys.add(candidate_key)

        candidate_entries.append(
            (candidate_key, candidate)
        )

    assessments_by_team = {}

    for team_name in team_names:
        team_assessments = {}

        for candidate_key, candidate in candidate_entries:
            route_profiles = (
                route_access_profiles_by_candidate.get(
                    candidate_key
                )
            )

            status = assess_team_candidate_route_access(
                candidate,
                team_name=team_name,
                capability_result=capability_result,
                route_access_profiles=route_profiles,
            )

            team_assessments[candidate_key] = status

        assessments_by_team[team_name] = team_assessments

    return assessments_by_team


def build_access_filtered_generation_candidates(
    candidates,
    *,
    candidate_access_by_team,
):
    """Retain candidates accessible to every supplied team.

    This function consumes completed candidate-level access
    assessments. It does not infer route eligibility from a
    TileCandidate's single access profile.

    Missing, unknown, invalid and inaccessible assessments
    all prevent a candidate from entering the board pool.
    """
    from collections.abc import Mapping

    if (
        not isinstance(candidate_access_by_team, Mapping)
        or not candidate_access_by_team
    ):
        return ()

    team_assessments = []

    for team_name, assessments in (
        candidate_access_by_team.items()
    ):
        if (
            not isinstance(team_name, str)
            or not team_name.strip()
            or not isinstance(assessments, Mapping)
        ):
            return ()

        team_assessments.append(assessments)

    eligible_candidates = []

    for candidate in candidates:
        candidate_key = build_generated_board_candidate_key(
            candidate
        )

        if all(
            assessments.get(candidate_key) == "accessible"
            for assessments in team_assessments
        ):
            eligible_candidates.append(candidate)

    return tuple(eligible_candidates)


def build_filtered_generation_candidates(
    candidates,
    kept_tile_keys=(),
    banned_tile_keys=(),
):
    kept_tile_keys = frozenset(kept_tile_keys or ())
    banned_tile_keys = frozenset(banned_tile_keys or ()) - kept_tile_keys

    return tuple(
        candidate
        for candidate in candidates
        if build_generated_board_candidate_key(candidate) not in banned_tile_keys
    )


def get_preselected_generation_candidates(
    candidates,
    kept_tile_keys=(),
):
    candidate_by_key = get_candidate_by_generated_board_key(
        candidates
    )

    kept_tile_keys = tuple(kept_tile_keys or ())
    missing = [key for key in kept_tile_keys if key not in candidate_by_key]
    if missing:
        raise BoardAssemblyError("Kept tile not found: " + ", ".join(map(str, missing)))

    return tuple(
        candidate_by_key[tile_key]
        for tile_key in kept_tile_keys or ()
        if tile_key in candidate_by_key
    )


def assemble_preview_board(
    generation_candidates,
    candidate_order_key=None,
    preselected_candidates=(),
):
    kwargs = {
        "candidate_order_key": candidate_order_key,
    }

    if preselected_candidates:
        kwargs["preselected_candidates"] = preselected_candidates

    return assemble_board_candidates(
        generation_candidates,
        **kwargs,
    )


def get_curated_generated_board_preview_summary(
    capability_profiles=None,
    kept_tile_keys=(),
    banned_tile_keys=(),
    generation_candidates=None,
    random_seed=None,
    candidate_access_by_team=None,
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

    if generation_candidates is None:
        generation_candidates = get_curated_tile_generation_candidates()

    # Access checks precede both kept-tile selection and bans.
    # No assessments supplied means legacy preview behaviour.
    if candidate_access_by_team is not None:
        generation_candidates = (
            build_access_filtered_generation_candidates(
                generation_candidates,
                candidate_access_by_team=candidate_access_by_team,
            )
        )

    preselected_candidates = get_preselected_generation_candidates(
        generation_candidates,
        kept_tile_keys=kept_tile_keys,
    )
    generation_candidates = build_filtered_generation_candidates(
        generation_candidates,
        kept_tile_keys=kept_tile_keys,
        banned_tile_keys=banned_tile_keys,
    )

    try:
        if random_seed is not None:
            board = assemble_randomised_preview_board(
                generation_candidates,
                seed=random_seed,
                preselected_candidates=preselected_candidates,
                balance_band_order_key=(None if candidate_order_key is None else lambda tile: candidate_order_key(tile)[0]),
            )
        else:
            board = assemble_preview_board(
                generation_candidates,
                candidate_order_key=candidate_order_key,
                preselected_candidates=preselected_candidates,
            )
    except BoardAssemblyError as error:
        if candidate_order_key is None:
            raise

        capability_ordering_fell_back = True
        capability_ordering_fallback_reason = str(error)

        if random_seed is not None:
            board = assemble_randomised_preview_board(
                generation_candidates,
                seed=random_seed,
                preselected_candidates=preselected_candidates,
            )
        else:
            board = assemble_preview_board(
                generation_candidates,
                preselected_candidates=preselected_candidates,
            )

    return build_generated_board_preview_summary(
        board,
        capability_profiles=capability_profiles,
        capability_ordering_applied=capability_ordering_applied,
        capability_ordering_fell_back=capability_ordering_fell_back,
        capability_ordering_fallback_reason=capability_ordering_fallback_reason,
    )


def assemble_randomised_preview_board(generation_candidates, seed=None, max_attempts=50, preselected_candidates=(), balance_band_order_key=None):
    """Assemble a valid board using reproducibly shuffled candidate orders."""
    from random import Random
    from utils.board_generation import BoardAssemblyError

    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")

    rng = Random(seed)
    candidates = tuple(generation_candidates)
    last_error = None
    for _ in range(max_attempts):
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        if balance_band_order_key is not None:
            shuffled.sort(key=balance_band_order_key)
        try:
            return assemble_preview_board(shuffled, preselected_candidates=preselected_candidates)
        except BoardAssemblyError as exc:
            last_error = exc

    raise BoardAssemblyError(f"Could not assemble a valid randomised board after {max_attempts} attempts.") from last_error
