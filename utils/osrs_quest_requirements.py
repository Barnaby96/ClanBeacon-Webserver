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
class QuestUnmeasuredCondition:
    '''A genuine requirement not independently measured by WOM.

    Planning assumptions do not establish player inventory,
    quest progress, travel access or actual route completion.
    '''

    quest_id: str
    condition_id: str
    condition_kind: str
    detail: str
    source_wikitext_sha256: str
    evidence_status: str = "NOT_INDEPENDENTLY_MEASURED"
    planning_policy: str = "ASSUMED_FOR_PLANNING_ONLY"
    partial_quest_id: str | None = None
    alternative_skill_route: tuple[str, int, str] | None = None

    def __post_init__(self):
        for name in ("quest_id", "condition_id"):
            value = getattr(self, name)

            if (
                not isinstance(value, str)
                or not value
                or canonical_id(value) != value
            ):
                raise ValueError(
                    f"Invalid unmeasured condition {name}"
                )

        if (
            not isinstance(self.detail, str)
            or not self.detail.strip()
            or self.detail != self.detail.strip()
        ):
            raise ValueError(
                "Unmeasured condition requires a description"
            )

        digest = self.source_wikitext_sha256

        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef"
                   for character in digest)
        ):
            raise ValueError(
                "Unmeasured condition requires a source fingerprint"
            )

        if (
            self.evidence_status != "NOT_INDEPENDENTLY_MEASURED"
            or self.planning_policy != "ASSUMED_FOR_PLANNING_ONLY"
        ):
            raise ValueError(
                "Unmeasured conditions cannot claim verified access"
            )

        if self.condition_kind == "PARTIAL_QUEST_PROGRESSION":
            if (
                not isinstance(self.partial_quest_id, str)
                or not self.partial_quest_id
                or canonical_id(self.partial_quest_id)
                != self.partial_quest_id
                or self.partial_quest_id == self.quest_id
                or self.alternative_skill_route is not None
            ):
                raise ValueError(
                    "Invalid partial quest progression condition"
                )

        elif self.condition_kind == "ALTERNATIVE_SKILL_OR_NON_SKILL":
            route = self.alternative_skill_route

            if (
                self.partial_quest_id is not None
                or not isinstance(route, tuple)
                or len(route) != 3
            ):
                raise ValueError(
                    "Invalid alternative skill route"
                )

            skill, level, boostability = route

            if (
                not isinstance(skill, str)
                or not skill
                or canonical_id(skill) != skill
                or type(level) is not int
                or level < 1
                or boostability not in ("yes", "no")
            ):
                raise ValueError(
                    "Invalid alternative skill threshold"
                )

        else:
            raise ValueError(
                "Unsupported unmeasured quest condition kind"
            )


@dataclass(frozen=True)
class QuestRequirement:
    quest_id: str
    display_name: str
    direct_skill_requirements: dict[str, int] = field(default_factory=dict)
    prerequisite_quest_ids: tuple[str, ...] = field(default_factory=tuple)
    access_flags: frozenset[AccessFlag] = field(default_factory=frozenset)
    direct_skill_boostability: dict[str, str] = field(default_factory=dict)
    non_skill_conditions: tuple[QuestUnmeasuredCondition, ...] = field(
        default_factory=tuple
    )

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

        # Boostability is optional metadata. An absent entry
        # preserves legacy behaviour without claiming the
        # requirement is necessarily unboostable.
        if not isinstance(self.direct_skill_boostability, dict):
            raise ValueError(
                "Direct skill boostability must be a dictionary."
            )

        normalised_boostability = {}

        for skill_id, boostability in (
            self.direct_skill_boostability.items()
        ):
            if not isinstance(skill_id, str):
                raise ValueError(
                    "Boostability skill IDs must be strings."
                )

            canonical_skill_id = canonical_id(skill_id)

            if canonical_skill_id not in (
                self.direct_skill_requirements
            ):
                raise ValueError(
                    "Boostability references an unknown direct "
                    f"skill requirement: {skill_id}"
                )

            if boostability not in ("yes", "no", "unknown"):
                raise ValueError(
                    "Boostability must be yes, no or unknown."
                )

            if canonical_skill_id in normalised_boostability:
                raise ValueError(
                    "Duplicate boostability skill ID: "
                    f"{canonical_skill_id}"
                )

            normalised_boostability[
                canonical_skill_id
            ] = boostability

        object.__setattr__(
            self,
            "direct_skill_boostability",
            normalised_boostability
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

        conditions = self.non_skill_conditions

        if not isinstance(conditions, (tuple, list)):
            raise ValueError(
                "Non-skill conditions must be a sequence"
            )

        identifiers = set()

        for condition in conditions:
            if (
                not isinstance(condition, QuestUnmeasuredCondition)
                or condition.quest_id != canonical_quest_id
                or condition.condition_id in identifiers
            ):
                raise ValueError(
                    "Invalid or duplicate quest non-skill condition"
                )

            identifiers.add(condition.condition_id)

        object.__setattr__(
            self,
            "non_skill_conditions",
            tuple(conditions)
        )


@dataclass(frozen=True)
class ResolvedQuestRequirements:
    quest_ids: tuple[str, ...]
    effective_skill_requirements: dict[str, int]
    access_flags: frozenset[AccessFlag]
    skill_boostability_thresholds: dict[str, dict[str, int]] = field(
        default_factory=dict
    )
    non_skill_conditions: tuple[QuestUnmeasuredCondition, ...] = field(
        default_factory=tuple
    )


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
    resolved_skill_thresholds = {}
    resolved_access_flags = set()
    resolved_non_skill_conditions = []
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

        # Preserve independent thresholds for each category.
        # Missing legacy metadata is unknown, not "no".
        for skill_id, required_level in (
            quest.direct_skill_requirements.items()
        ):
            boostability = (
                quest.direct_skill_boostability.get(
                    skill_id,
                    "unknown"
                )
            )

            thresholds = resolved_skill_thresholds.setdefault(
                skill_id,
                {}
            )

            thresholds[boostability] = max(
                thresholds.get(boostability, 0),
                required_level
            )

        resolved_access_flags.update(
            quest.access_flags
        )
        resolved_non_skill_conditions.extend(
            quest.non_skill_conditions
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
        skill_boostability_thresholds={
            skill_id: dict(thresholds)
            for skill_id, thresholds
            in resolved_skill_thresholds.items()
        },
        non_skill_conditions=tuple(
            resolved_non_skill_conditions
        ),
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
        skill_boostability_thresholds=(
            resolved_requirements.skill_boostability_thresholds
        ),
        non_skill_conditions=(
            resolved_requirements.non_skill_conditions
        ),
    )
