"""Regression tests for quest skill boostability and player access."""

import pytest

from utils.board_generation import AccessFlag, AccessProfile
from utils.osrs_player_access import assess_player_source_access
from utils.osrs_quest_requirements import (
    QuestRequirement,
    build_access_profile_from_quests,
)
from utils.osrs_quest_data import (
    build_curated_access_profile_from_quests,
    get_curated_quest_requirements,
)
from utils.osrs_skill_boostability import classify_skill_requirement


def assess(profile, levels, verified=True):
    return assess_player_source_access(
        profile,
        levels,
        source_id="boostability_regression_test",
        requirements_verified=verified,
    )


def build_mixed_quest_profile():
    quests = (
        QuestRequirement(
            quest_id="test_smithing_base",
            display_name="Smithing Base",
            direct_skill_requirements={"smithing": 15},
            direct_skill_boostability={"smithing": "no"},
        ),
        QuestRequirement(
            quest_id="test_smithing_advanced",
            display_name="Smithing Advanced",
            direct_skill_requirements={"smithing": 30},
            direct_skill_boostability={"smithing": "yes"},
            prerequisite_quest_ids=("test_smithing_base",),
        ),
        QuestRequirement(
            quest_id="test_smithing_final",
            display_name="Smithing Final",
            direct_skill_requirements={"smithing": 25},
            direct_skill_boostability={"smithing": "yes"},
            prerequisite_quest_ids=("test_smithing_advanced",),
        ),
    )

    return build_access_profile_from_quests(
        ("test_smithing_final",),
        quests,
    )


def test_quest_chain_preserves_separate_thresholds():
    profile = build_mixed_quest_profile()

    assert profile.effective_skill_requirements == {
        "smithing": 30,
    }

    assert profile.skill_boostability_thresholds == {
        "smithing": {
            "no": 15,
            "yes": 30,
        },
    }

    assert AccessFlag.QUEST_LOCKED in profile.access_flags


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (1, "inaccessible"),
        (12, "inaccessible"),
        (14, "inaccessible"),
        (15, "unknown"),
        (20, "unknown"),
        (25, "unknown"),
        (29, "unknown"),
        (30, "accessible"),
        (40, "accessible"),
    ],
)
def test_mixed_quest_chain_eligibility(level, expected):
    profile = build_mixed_quest_profile()

    assert assess(profile, {"smithing": level}) == expected


def test_unboostable_requirement_takes_precedence():
    profile = AccessProfile(
        effective_skill_requirements={
            "hunter": 27,
            "fishing": 10,
        },
        skill_boostability_thresholds={
            "hunter": {"yes": 27},
            "fishing": {"no": 10},
        },
    )

    assert assess(
        profile,
        {"hunter": 15, "fishing": 5},
    ) == "inaccessible"

    assert assess(
        profile,
        {"hunter": 15, "fishing": 10},
    ) == "unknown"

    assert assess(
        profile,
        {"hunter": 27, "fishing": 10},
    ) == "accessible"


def test_boostable_requirement_does_not_grant_access():
    profile = AccessProfile(
        effective_skill_requirements={"hunter": 27},
        skill_boostability_thresholds={
            "hunter": {"yes": 27},
        },
    )

    assert assess(
        profile, {"hunter": 20}
    ) == "unknown"

    assert assess(
        profile, {"hunter": 27}
    ) == "accessible"


def test_missing_and_unverified_evidence_remains_unknown():
    profile = build_mixed_quest_profile()

    assert assess(profile, {}) == "unknown"
    assert assess(profile, {"smithing": True}) == "unknown"

    assert assess(
        profile,
        {"smithing": 99},
        verified=False,
    ) == "unknown"


def test_legacy_requirements_remain_strict():
    profile = AccessProfile(
        effective_skill_requirements={"hunter": 27},
    )

    assert profile.skill_boostability_thresholds == {}

    assert assess(
        profile, {"hunter": 26}
    ) == "inaccessible"

    assert assess(
        profile, {"hunter": 27}
    ) == "accessible"


def test_unknown_boostability_does_not_assume_boosting():
    profile = AccessProfile(
        effective_skill_requirements={"hunter": 27},
        skill_boostability_thresholds={
            "hunter": {"unknown": 27},
        },
    )

    assert assess(
        profile, {"hunter": 26}
    ) == "inaccessible"

    assert assess(
        profile, {"hunter": 27}
    ) == "accessible"


@pytest.mark.parametrize(
    ("required", "boostable", "player", "expected"),
    [
        (27, "yes", 20, "BOOST_REQUIRED_UNCONFIRMED"),
        (27, "yes", 27, "MEETS_RECORDED_LEVEL"),
        (27, "no", 20, "BELOW_NONBOOSTABLE"),
        (27, "unknown", 20, "UNKNOWN_BOOSTABILITY"),
        (27, "yes", None, "UNKNOWN_SKILL"),
    ],
)
def test_existing_boostability_classifier(
    required, boostable, player, expected
):
    assert classify_skill_requirement(
        required, boostable, player
    ) == expected


def test_existing_activated_quests_keep_level_behaviour():
    curated = {
        quest.quest_id
        for quest in get_curated_quest_requirements()
    }

    assert "fishing_contest" in curated
    assert "sleeping_giants" in curated

    fishing = build_curated_access_profile_from_quests(
        ("fishing_contest",)
    )

    sleeping = build_curated_access_profile_from_quests(
        ("sleeping_giants",)
    )

    assert assess(
        fishing, {"fishing": 9}
    ) == "inaccessible"

    assert assess(
        fishing, {"fishing": 10}
    ) == "accessible"

    assert assess(
        sleeping, {"smithing": 14}
    ) == "inaccessible"

    assert assess(
        sleeping, {"smithing": 15}
    ) == "accessible"
