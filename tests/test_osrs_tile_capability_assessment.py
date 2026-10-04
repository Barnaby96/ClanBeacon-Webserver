from decimal import Decimal

from utils.board_generation import (
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
)
from utils.osrs_capability_profiles import (
    CapabilityProfile,
    CapabilityProfileSet,
)
from utils.osrs_tile_capability_assessment import (
    assess_and_sort_candidates_by_capability_risk,
    assess_candidate_capability,
    sort_candidate_capability_assessments_by_risk,
)


def build_candidate(source_id="zulrah"):
    return TileCandidate(
        title="Obtain 1 Zulrah unique",
        point_value=1,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.DROP,
                display_text="Obtain 1 Zulrah unique",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.TEAM_SUM,
                source_id=source_id,
                expected_rolls=Decimal("155.9"),
            ),
        ),
    )


def build_profile_set():
    return CapabilityProfileSet(
        source="teams",
        profiles=(
            CapabilityProfile(
                profile_id="1",
                display_name="Team One",
                player_count=5,
                scores={
                    "solo_boss_score": 10,
                },
            ),
            CapabilityProfile(
                profile_id="2",
                display_name="Team Two",
                player_count=5,
                scores={
                    "solo_boss_score": 0,
                },
            ),
            CapabilityProfile(
                profile_id="3",
                display_name="Team Three",
                player_count=5,
                scores={
                    "solo_boss_score": 4,
                },
            ),
        ),
    )


def test_assess_candidate_capability_uses_mapped_score_field():
    assessment = assess_candidate_capability(
        build_candidate(),
        build_profile_set(),
    )

    assert assessment.candidate_title == "Obtain 1 Zulrah unique"
    assert assessment.capability_score_field == "solo_boss_score"
    assert assessment.profile_scores == (
        (
            "Team One",
            10.0,
        ),
        (
            "Team Two",
            0.0,
        ),
        (
            "Team Three",
            4.0,
        ),
    )
    assert assessment.minimum_score == 0
    assert assessment.maximum_score == 10
    assert assessment.average_score == 14 / 3
    assert assessment.zero_score_profile_count == 1
    assert assessment.score_gap == 10
    assert assessment.has_profile_data
    assert not assessment.all_profiles_have_score
    assert assessment.has_score_gap
    assert assessment.has_zero_score_gap


def test_assess_candidate_capability_without_mapping_returns_empty_assessment():
    assessment = assess_candidate_capability(
        build_candidate(
            source_id="unknown_source"
        ),
        build_profile_set(),
    )

    assert assessment.capability_score_field is None
    assert assessment.profile_scores == ()
    assert assessment.minimum_score is None
    assert assessment.maximum_score is None
    assert assessment.average_score is None
    assert assessment.zero_score_profile_count == 0
    assert assessment.score_gap is None
    assert not assessment.has_profile_data


def test_assess_candidate_capability_handles_empty_profiles():
    assessment = assess_candidate_capability(
        build_candidate(),
        CapabilityProfileSet(
            source="teams",
            profiles=(),
        ),
    )

    assert assessment.capability_score_field == "solo_boss_score"
    assert assessment.profile_scores == ()
    assert assessment.minimum_score is None
    assert assessment.maximum_score is None
    assert assessment.average_score is None
    assert assessment.zero_score_profile_count == 0
    assert assessment.score_gap is None
    assert not assessment.has_profile_data


def test_capability_assessment_balance_band_flags_zero_score_gap():
    assessment = assess_candidate_capability(
        build_candidate(),
        build_profile_set(),
    )

    assert assessment.score_ratio is None
    assert assessment.balance_band == "zero_score_gap"


def test_capability_assessment_balance_band_flags_high_gap():
    profile_set = CapabilityProfileSet(
        source="teams",
        profiles=(
            CapabilityProfile(
                profile_id="1",
                display_name="Team One",
                player_count=5,
                scores={
                    "solo_boss_score": 9,
                },
            ),
            CapabilityProfile(
                profile_id="2",
                display_name="Team Two",
                player_count=5,
                scores={
                    "solo_boss_score": 3,
                },
            ),
        ),
    )

    assessment = assess_candidate_capability(
        build_candidate(),
        profile_set,
    )

    assert assessment.score_ratio == 3
    assert assessment.balance_band == "high_gap"


def test_capability_assessment_balance_band_flags_balanced_scores():
    profile_set = CapabilityProfileSet(
        source="teams",
        profiles=(
            CapabilityProfile(
                profile_id="1",
                display_name="Team One",
                player_count=5,
                scores={
                    "solo_boss_score": 9,
                },
            ),
            CapabilityProfile(
                profile_id="2",
                display_name="Team Two",
                player_count=5,
                scores={
                    "solo_boss_score": 6,
                },
            ),
        ),
    )

    assessment = assess_candidate_capability(
        build_candidate(),
        profile_set,
    )

    assert assessment.balance_band == "balanced"


def test_capability_assessment_balance_band_flags_unmapped_candidates():
    assessment = assess_candidate_capability(
        build_candidate(
            source_id="unknown_source"
        ),
        build_profile_set(),
    )

    assert assessment.balance_band == "unmapped"


def test_sort_candidate_capability_assessments_by_risk_orders_worst_first():
    zero_gap = assess_candidate_capability(
        build_candidate(),
        build_profile_set(),
    )

    high_gap = assess_candidate_capability(
        build_candidate(),
        CapabilityProfileSet(
            source="teams",
            profiles=(
                CapabilityProfile(
                    profile_id="1",
                    display_name="Team One",
                    player_count=5,
                    scores={
                        "solo_boss_score": 9,
                    },
                ),
                CapabilityProfile(
                    profile_id="2",
                    display_name="Team Two",
                    player_count=5,
                    scores={
                        "solo_boss_score": 3,
                    },
                ),
            ),
        ),
    )

    balanced = assess_candidate_capability(
        build_candidate(),
        CapabilityProfileSet(
            source="teams",
            profiles=(
                CapabilityProfile(
                    profile_id="1",
                    display_name="Team One",
                    player_count=5,
                    scores={
                        "solo_boss_score": 9,
                    },
                ),
                CapabilityProfile(
                    profile_id="2",
                    display_name="Team Two",
                    player_count=5,
                    scores={
                        "solo_boss_score": 6,
                    },
                ),
            ),
        ),
    )

    sorted_assessments = sort_candidate_capability_assessments_by_risk(
        (
            balanced,
            zero_gap,
            high_gap,
        )
    )

    assert tuple(
        assessment.balance_band
        for assessment in sorted_assessments
    ) == (
        "zero_score_gap",
        "high_gap",
        "balanced",
    )


def test_assess_and_sort_candidates_by_capability_risk_returns_worst_first():
    risky_candidate = build_candidate(
        source_id="zulrah"
    )
    unmapped_candidate = build_candidate(
        source_id="unknown_source"
    )

    sorted_assessments = assess_and_sort_candidates_by_capability_risk(
        (
            unmapped_candidate,
            risky_candidate,
        ),
        build_profile_set(),
    )

    assert tuple(
        assessment.candidate_title
        for assessment in sorted_assessments
    ) == (
        "Obtain 1 Zulrah unique",
        "Obtain 1 Zulrah unique",
    )
    assert tuple(
        assessment.balance_band
        for assessment in sorted_assessments
    ) == (
        "zero_score_gap",
        "unmapped",
    )
