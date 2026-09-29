import pytest

from utils.board_generation import AccessConfidence, AccessFlag
from utils.osrs_content_access import (
    ContentAccessError,
    ContentAccessRequirement,
    build_access_profile_for_content,
    build_content_access_lookup,
    get_content_access_requirement,
    get_curated_content_access_requirements,
)


def test_curated_content_access_ids_are_unique():
    content_ids = [
        requirement.content_id
        for requirement in get_curated_content_access_requirements()
    ]

    assert len(content_ids) == len(set(content_ids))


def test_get_content_access_requirement_normalises_content_id():
    requirement = get_content_access_requirement(
        "Zulrah"
    )

    assert requirement.content_id == "zulrah"
    assert requirement.display_name == "Zulrah"
    assert requirement.required_quest_ids == (
        "regicide",
    )


def test_get_content_access_requirement_rejects_unknown_content():
    with pytest.raises(
        ContentAccessError,
        match="Unknown content access id"
    ):
        get_content_access_requirement(
            "missing_content"
        )


def test_build_content_access_lookup_rejects_duplicate_ids():
    requirements = [
        ContentAccessRequirement(
            content_id="zulrah",
            display_name="Zulrah",
        ),
        ContentAccessRequirement(
            content_id="Zulrah",
            display_name="Duplicate Zulrah",
        ),
    ]

    with pytest.raises(
        ContentAccessError,
        match="Duplicate content access id"
    ):
        build_content_access_lookup(
            requirements
        )


def test_build_access_profile_for_zulrah_content():
    profile = build_access_profile_for_content(
        "zulrah"
    )

    assert profile.effective_skill_requirements == {
        "agility": 56,
        "ranged": 25,
        "crafting": 10,
    }
    assert profile.recommended_skill_requirements == {}
    assert profile.access_flags == frozenset(
        {
            AccessFlag.QUEST_LOCKED,
        }
    )
    assert profile.access_confidence == AccessConfidence.MEDIUM


def test_build_access_profile_for_vorkath_content():
    profile = build_access_profile_for_content(
        "vorkath"
    )

    assert profile.effective_skill_requirements == {
        "magic": 75,
        "smithing": 70,
        "mining": 68,
        "crafting": 62,
        "agility": 60,
        "thieving": 60,
        "woodcutting": 55,
        "cooking": 53,
        "fishing": 53,
        "construction": 50,
        "hitpoints": 50,
        "strength": 50,
        "firemaking": 49,
        "herblore": 45,
        "prayer": 42,
        "defence": 40,
        "ranged": 30,
        "slayer": 18,
    }
    assert AccessFlag.QUEST_LOCKED in profile.access_flags


def test_build_access_profile_for_darkmeyer_content():
    profile = build_access_profile_for_content(
        "darkmeyer"
    )

    assert profile.effective_skill_requirements == {
        "woodcutting": 62,
        "fletching": 60,
        "crafting": 56,
        "agility": 52,
        "attack": 50,
        "slayer": 50,
        "magic": 49,
        "herblore": 40,
        "strength": 40,
        "thieving": 22,
        "mining": 20,
        "construction": 5,
    }
    assert AccessFlag.QUEST_LOCKED in profile.access_flags
