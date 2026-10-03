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
