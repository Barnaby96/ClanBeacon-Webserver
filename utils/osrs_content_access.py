from dataclasses import dataclass, field

from utils.board_generation import (
    AccessConfidence,
    AccessFlag,
    canonical_id,
    normalise_skill_requirements,
)
from utils.osrs_quest_data import (
    DARKMEYER_REQUIRED_QUEST_IDS,
    VORKATH_REQUIRED_QUEST_IDS,
    ZULRAH_REQUIRED_QUEST_IDS,
    build_curated_access_profile_from_quests,
)


class ContentAccessError(ValueError):
    pass


@dataclass(frozen=True)
class ContentAccessRequirement:
    content_id: str
    display_name: str
    required_quest_ids: tuple[str, ...] = field(default_factory=tuple)
    recommended_skill_requirements: dict[str, int] = field(default_factory=dict)
    additional_access_flags: frozenset[AccessFlag] = field(default_factory=frozenset)
    access_confidence: AccessConfidence = AccessConfidence.MEDIUM

    def __post_init__(self):
        canonical_content_id = canonical_id(
            self.content_id
        )

        if canonical_content_id is None or canonical_content_id == "":
            raise ValueError(
                "Content access requirement must have a content_id."
            )

        object.__setattr__(
            self,
            "content_id",
            canonical_content_id
        )
        object.__setattr__(
            self,
            "required_quest_ids",
            tuple(
                canonical_id(quest_id)
                for quest_id in self.required_quest_ids
                if canonical_id(quest_id) is not None
                and canonical_id(quest_id) != ""
            )
        )
        object.__setattr__(
            self,
            "recommended_skill_requirements",
            normalise_skill_requirements(
                self.recommended_skill_requirements,
                f"{self.display_name} recommended"
            )
        )
        object.__setattr__(
            self,
            "additional_access_flags",
            frozenset(
                self.additional_access_flags
            )
        )


CURATED_CONTENT_ACCESS_REQUIREMENTS = (
    ContentAccessRequirement(
        content_id="zulrah",
        display_name="Zulrah",
        required_quest_ids=ZULRAH_REQUIRED_QUEST_IDS,
    ),
    ContentAccessRequirement(
        content_id="vorkath",
        display_name="Vorkath",
        required_quest_ids=VORKATH_REQUIRED_QUEST_IDS,
    ),
    ContentAccessRequirement(
        content_id="darkmeyer",
        display_name="Darkmeyer",
        required_quest_ids=DARKMEYER_REQUIRED_QUEST_IDS,
    ),
)


def get_curated_content_access_requirements():
    return CURATED_CONTENT_ACCESS_REQUIREMENTS


def build_content_access_lookup(content_access_requirements=None):
    if content_access_requirements is None:
        content_access_requirements = CURATED_CONTENT_ACCESS_REQUIREMENTS

    lookup = {}

    for requirement in content_access_requirements:
        if requirement.content_id in lookup:
            raise ContentAccessError(
                f"Duplicate content access id: {requirement.content_id}"
            )

        lookup[requirement.content_id] = requirement

    return lookup


def get_content_access_requirement(content_id, content_access_requirements=None):
    lookup = build_content_access_lookup(
        content_access_requirements
    )
    content_id = canonical_id(
        content_id
    )

    if content_id not in lookup:
        raise ContentAccessError(
            f"Unknown content access id: {content_id}"
        )

    return lookup[content_id]


def build_access_profile_for_content(content_id, content_access_requirements=None):
    requirement = get_content_access_requirement(
        content_id,
        content_access_requirements
    )

    return build_curated_access_profile_from_quests(
        required_quest_ids=requirement.required_quest_ids,
        recommended_skill_requirements=requirement.recommended_skill_requirements,
        additional_access_flags=requirement.additional_access_flags,
        access_confidence=requirement.access_confidence,
    )
