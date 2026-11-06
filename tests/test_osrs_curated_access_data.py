"""Reusable validation of curated OSRS access data.

These checks validate every registered quest and content
source, including future additions. They check data
integrity, not independent factual accuracy against OSRS.
"""

from collections.abc import Mapping

from utils.board_generation import (
    AccessConfidence,
    AccessFlag,
)
from utils.osrs_quest_data import (
    get_curated_quest_requirements,
    resolve_curated_quest_skill_requirements,
)
from utils.osrs_content_access import (
    get_curated_content_access_requirements,
    build_access_profile_for_content,
)


def _check_skill_requirements(requirements, context):
    assert isinstance(requirements, Mapping), context

    for skill, level in requirements.items():
        assert isinstance(skill, str), context
        assert skill and skill == skill.strip(), context
        assert skill == skill.lower(), context

        assert type(level) is int, (
            context, skill, level
        )
        assert 1 <= level <= 99, (
            context, skill, level
        )


def test_all_curated_quest_chains_resolve():
    quests = tuple(get_curated_quest_requirements())

    assert quests, "Curated quest database is empty"

    seen_ids = set()

    for quest in quests:
        quest_id = quest.quest_id

        assert quest_id not in seen_ids, (
            "Duplicate quest ID", quest_id
        )
        seen_ids.add(quest_id)

        _check_skill_requirements(
            quest.direct_skill_requirements,
            quest_id,
        )

        # Exercise every prerequisite chain, rather
        # than only the ones currently used by Bingo.
        resolved = resolve_curated_quest_skill_requirements(
            (quest_id,)
        )

        assert quest_id in resolved.quest_ids

        _check_skill_requirements(
            resolved.effective_skill_requirements,
            quest_id,
        )

        assert AccessFlag.QUEST_LOCKED in (
            resolved.access_flags
        )


def test_all_curated_content_access_profiles_resolve():
    records = tuple(
        get_curated_content_access_requirements()
    )

    assert records, "Curated content access database is empty"

    seen_ids = set()

    for record in records:
        content_id = record.content_id

        assert content_id not in seen_ids, (
            "Duplicate content ID", content_id
        )
        seen_ids.add(content_id)

        assert isinstance(
            record.access_confidence,
            AccessConfidence,
        ), content_id

        _check_skill_requirements(
            record.recommended_skill_requirements,
            content_id,
        )

        assert all(
            isinstance(flag, AccessFlag)
            for flag in record.additional_access_flags
        ), content_id

        resolved = resolve_curated_quest_skill_requirements(
            record.required_quest_ids
        )

        profile = build_access_profile_for_content(
            content_id
        )

        # Every prerequisite quest's skill requirements
        # must carry into the resulting source profile.
        assert (
            profile.effective_skill_requirements
            == resolved.effective_skill_requirements
        ), content_id

        assert (
            profile.recommended_skill_requirements
            == record.recommended_skill_requirements
        ), content_id

        expected_flags = frozenset({
            *resolved.access_flags,
            *record.additional_access_flags,
        })

        assert profile.access_flags == expected_flags, (
            content_id,
            profile.access_flags,
            expected_flags,
        )

        _check_skill_requirements(
            profile.effective_skill_requirements,
            content_id,
        )
