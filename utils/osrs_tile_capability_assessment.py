from dataclasses import dataclass

from utils.osrs_tile_capability_mapping import (
    get_primary_capability_score_field_for_candidate,
)


CAPABILITY_BALANCE_UNMAPPED = "unmapped"
CAPABILITY_BALANCE_NO_PROFILE_DATA = "no_profile_data"
CAPABILITY_BALANCE_NO_SIGNAL = "no_capability_signal"
CAPABILITY_BALANCE_BALANCED = "balanced"
CAPABILITY_BALANCE_MODERATE_GAP = "moderate_gap"
CAPABILITY_BALANCE_HIGH_GAP = "high_gap"
CAPABILITY_BALANCE_ZERO_SCORE_GAP = "zero_score_gap"


CAPABILITY_BALANCE_BAND_SORT_ORDER = {
    CAPABILITY_BALANCE_ZERO_SCORE_GAP: 0,
    CAPABILITY_BALANCE_HIGH_GAP: 1,
    CAPABILITY_BALANCE_MODERATE_GAP: 2,
    CAPABILITY_BALANCE_BALANCED: 3,
    CAPABILITY_BALANCE_NO_SIGNAL: 4,
    CAPABILITY_BALANCE_NO_PROFILE_DATA: 5,
    CAPABILITY_BALANCE_UNMAPPED: 6,
}


CAPABILITY_SCORE_FIELD_LABELS = {
    "skilling_score": "Skilling",
    "solo_boss_score": "Solo boss",
    "slayer_boss_score": "Slayer boss",
    "dt2_boss_score": "DT2 boss",
    "endgame_boss_score": "Endgame boss",
    "group_boss_score": "Group boss",
    "raid_score": "Raid",
    "wilderness_boss_score": "Wilderness boss",
    "midgame_boss_score": "Midgame boss",
    "activity_boss_score": "Activity boss",
    "clue_activity_score": "Clue activity",
}


CAPABILITY_BALANCE_WARNING_LEVELS = {
    CAPABILITY_BALANCE_ZERO_SCORE_GAP: "danger",
    CAPABILITY_BALANCE_HIGH_GAP: "danger",
    CAPABILITY_BALANCE_MODERATE_GAP: "warning",
    CAPABILITY_BALANCE_BALANCED: "none",
    CAPABILITY_BALANCE_NO_SIGNAL: "info",
    CAPABILITY_BALANCE_NO_PROFILE_DATA: "info",
    CAPABILITY_BALANCE_UNMAPPED: "info",
}


def format_capability_score(value):
    if value is None:
        return "n/a"

    value = float(
        value
    )

    if value.is_integer():
        return str(
            int(
                value
            )
        )

    return f"{value:.1f}"


@dataclass(frozen=True)
class CandidateCapabilityAssessment:
    candidate_title: str
    capability_score_field: str | None
    profile_scores: tuple[tuple[str, float], ...]
    minimum_score: float | None
    maximum_score: float | None
    average_score: float | None
    zero_score_profile_count: int
    score_gap: float | None

    @property
    def has_profile_data(self):
        return bool(
            self.profile_scores
        )

    @property
    def all_profiles_have_score(self):
        return (
            self.has_profile_data
            and self.zero_score_profile_count == 0
        )

    @property
    def has_score_gap(self):
        return (
            self.score_gap is not None
            and self.score_gap > 0
        )

    @property
    def has_zero_score_gap(self):
        return (
            self.has_profile_data
            and self.zero_score_profile_count > 0
            and self.maximum_score is not None
            and self.maximum_score > 0
        )

    @property
    def score_ratio(self):
        if (
            self.minimum_score is None
            or self.maximum_score is None
            or self.minimum_score <= 0
        ):
            return None

        return self.maximum_score / self.minimum_score

    @property
    def balance_band(self):
        if self.capability_score_field is None:
            return CAPABILITY_BALANCE_UNMAPPED

        if not self.has_profile_data:
            return CAPABILITY_BALANCE_NO_PROFILE_DATA

        if self.maximum_score is None or self.maximum_score <= 0:
            return CAPABILITY_BALANCE_NO_SIGNAL

        if self.has_zero_score_gap:
            return CAPABILITY_BALANCE_ZERO_SCORE_GAP

        if self.score_ratio is None:
            return CAPABILITY_BALANCE_NO_SIGNAL

        if self.score_ratio >= 3:
            return CAPABILITY_BALANCE_HIGH_GAP

        if self.score_ratio >= 2:
            return CAPABILITY_BALANCE_MODERATE_GAP

        return CAPABILITY_BALANCE_BALANCED

    @property
    def score_field_label(self):
        if self.capability_score_field is None:
            return None

        return CAPABILITY_SCORE_FIELD_LABELS.get(
            self.capability_score_field,
            self.capability_score_field,
        )

    @property
    def warning_level(self):
        return CAPABILITY_BALANCE_WARNING_LEVELS.get(
            self.balance_band,
            "info",
        )

    @property
    def summary_text(self):
        score_field_label = self.score_field_label

        if score_field_label is None:
            return "No capability mapping is available for this tile."

        if not self.has_profile_data:
            return (
                "No capability profile data is available for "
                f"{score_field_label} tiles."
            )

        if self.maximum_score is None or self.maximum_score <= 0:
            return (
                "No profile has a recorded "
                f"{score_field_label} capability score."
            )

        if self.has_zero_score_gap:
            return (
                "At least one profile has no recorded "
                f"{score_field_label} capability score, while another has "
                f"{format_capability_score(self.maximum_score)}."
            )

        if self.score_ratio is not None and self.score_ratio >= 2:
            return (
                f"{score_field_label} capability varies from "
                f"{format_capability_score(self.minimum_score)} to "
                f"{format_capability_score(self.maximum_score)} "
                f"({self.score_ratio:.1f}x gap)."
            )

        return (
            f"{score_field_label} capability looks broadly balanced "
            f"({format_capability_score(self.minimum_score)} to "
            f"{format_capability_score(self.maximum_score)})."
        )


def assess_candidate_capability(candidate, capability_profiles):
    score_field = get_primary_capability_score_field_for_candidate(
        candidate
    )

    if score_field is None:
        return CandidateCapabilityAssessment(
            candidate_title=candidate.title,
            capability_score_field=None,
            profile_scores=(),
            minimum_score=None,
            maximum_score=None,
            average_score=None,
            zero_score_profile_count=0,
            score_gap=None,
        )

    profile_scores = tuple(
        (
            profile.display_name,
            profile.score_for(
                score_field
            ),
        )
        for profile in capability_profiles.profiles
    )

    if not profile_scores:
        return CandidateCapabilityAssessment(
            candidate_title=candidate.title,
            capability_score_field=score_field,
            profile_scores=(),
            minimum_score=None,
            maximum_score=None,
            average_score=None,
            zero_score_profile_count=0,
            score_gap=None,
        )

    scores = tuple(
        score
        for _, score in profile_scores
    )

    minimum_score = min(
        scores
    )
    maximum_score = max(
        scores
    )

    return CandidateCapabilityAssessment(
        candidate_title=candidate.title,
        capability_score_field=score_field,
        profile_scores=profile_scores,
        minimum_score=minimum_score,
        maximum_score=maximum_score,
        average_score=sum(
            scores
        )
        / len(
            scores
        ),
        zero_score_profile_count=sum(
            1
            for score in scores
            if score <= 0
        ),
        score_gap=maximum_score - minimum_score,
    )


def sort_candidate_capability_assessments_by_risk(assessments):
    return tuple(
        sorted(
            assessments,
            key=lambda assessment: (
                CAPABILITY_BALANCE_BAND_SORT_ORDER.get(
                    assessment.balance_band,
                    99,
                ),
                -(
                    assessment.score_gap
                    or 0
                ),
                assessment.candidate_title,
            ),
        )
    )


def assess_candidates_by_capability(candidates, capability_profiles):
    return tuple(
        assess_candidate_capability(
            candidate,
            capability_profiles,
        )
        for candidate in candidates
    )


def assess_and_sort_candidates_by_capability_risk(
    candidates,
    capability_profiles,
):
    return sort_candidate_capability_assessments_by_risk(
        assess_candidates_by_capability(
            candidates,
            capability_profiles,
        )
    )
