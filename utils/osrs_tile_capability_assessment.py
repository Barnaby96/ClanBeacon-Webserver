from dataclasses import dataclass

from utils.osrs_tile_capability_mapping import (
    get_primary_capability_score_field_for_candidate,
)


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
