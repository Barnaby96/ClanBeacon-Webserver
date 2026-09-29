from dataclasses import dataclass, field
from typing import Iterable

from utils.board_generation import (
    AccessConfidence,
    AccessFlag,
    AccessProfile,
    canonical_id,
    normalise_skill_requirements,
)


class QuestRequirementError(ValueError):
    pass


@dataclass(frozen=True)
class QuestRequirement:
    quest_id: str
    display_name: str
    direct_skill_requirements: dict[str, int] = field(default_factory=dict)
    prerequisite_quest_ids: tuple[str, ...] = field(default_factory=tuple)
    access_flags: frozenset[AccessFlag] = field(default_factory=frozenset)

    def __post_init__(self):
        canonical_quest_id = canonical_id(self.quest_id)

        if canonical_quest_id is None or canonical_quest_id == "":
            raise ValueError(
                "Quest requirement must have a quest_id."
            )

        object.__setattr__(
            self,
            "quest_id",
            canonical_quest_id
        )
        object.__setattr__(
            self,
            "direct_skill_requirements",
            normalise_skill_requirements(
                self.direct_skill_requirements,
                f"{self.display_name} direct"
            )
        )
        object.__setattr__(
            self,
            "prerequisite_quest_ids",
            tuple(
                canonical_id(quest_id)
                for quest_id in self.prerequisite_quest_ids
                if canonical_id(quest_id) is not None
                and canonical_id(quest_id) != ""
            )
        )
        object.__setattr__(
            self,
            "access_flags",
            frozenset(
                self.access_flags
            )
        )


@dataclass(frozen=True)
class ResolvedQuestRequirements:
    quest_ids: tuple[str, ...]
    effective_skill_requirements: dict[str, int]
    access_flags: frozenset[AccessFlag]


def build_quest_lookup(quest_requirements):
    lookup = {}

    for quest in quest_requirements:
        if quest.quest_id in lookup:
            raise QuestRequirementError(
                f"Duplicate quest requirement id: {quest.quest_id}"
            )

        lookup[quest.quest_id] = quest

    return lookup


def merge_skill_requirements(current_requirements, new_requirements):
    merged_requirements = dict(
        current_requirements
    )

    for skill_id, required_level in new_requirements.items():
        merged_requirements[skill_id] = max(
            merged_requirements.get(
                skill_id,
                0
            ),
            required_level
        )

    return merged_requirements


def resolve_quest_skill_requirements(required_quest_ids, quest_requirements):
    lookup = build_quest_lookup(
        quest_requirements
    )
    resolved_quest_ids = []
    resolved_skill_requirements = {}
    resolved_access_flags = set()
    permanently_seen = set()
    currently_seen = set()

    def visit(quest_id):
        quest_id = canonical_id(quest_id)

        if quest_id not in lookup:
            raise QuestRequirementError(
                f"Unknown quest requirement id: {quest_id}"
            )

        if quest_id in currently_seen:
            raise QuestRequirementError(
                f"Circular quest requirement chain detected at: {quest_id}"
            )

        if quest_id in permanently_seen:
            return

        currently_seen.add(
            quest_id
        )

        quest = lookup[quest_id]

        for prerequisite_quest_id in quest.prerequisite_quest_ids:
            visit(
                prerequisite_quest_id
            )

        nonlocal resolved_skill_requirements
        resolved_skill_requirements = merge_skill_requirements(
            resolved_skill_requirements,
            quest.direct_skill_requirements
        )
        resolved_access_flags.update(
            quest.access_flags
        )
        resolved_quest_ids.append(
            quest_id
        )

        currently_seen.remove(
            quest_id
        )
        permanently_seen.add(
            quest_id
        )

    for required_quest_id in required_quest_ids:
        visit(
            required_quest_id
        )

    if resolved_quest_ids:
        resolved_access_flags.add(
            AccessFlag.QUEST_LOCKED
        )

    return ResolvedQuestRequirements(
        quest_ids=tuple(resolved_quest_ids),
        effective_skill_requirements=resolved_skill_requirements,
        access_flags=frozenset(resolved_access_flags),
    )


def build_access_profile_from_quests(
    required_quest_ids,
    quest_requirements,
    recommended_skill_requirements=None,
    additional_access_flags=None,
    access_confidence=AccessConfidence.MEDIUM,
):
    resolved_requirements = resolve_quest_skill_requirements(
        required_quest_ids,
        quest_requirements
    )

    access_flags = set(
        resolved_requirements.access_flags
    )

    if additional_access_flags:
        access_flags.update(
            additional_access_flags
        )

    return AccessProfile(
        effective_skill_requirements=resolved_requirements.effective_skill_requirements,
        recommended_skill_requirements=recommended_skill_requirements or {},
        access_flags=frozenset(access_flags),
        access_confidence=access_confidence,
    )
