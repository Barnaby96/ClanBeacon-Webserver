"""Reviewable OSRS requirement expressions.

This module defines data structures only. It deliberately contains
no player eligibility evaluator. Unresolved routes cannot be
interpreted as satisfied conditions.
"""

import re
from dataclasses import dataclass, field

from utils.osrs_quest_skill_parser import SKILLS


GROUP_KINDS = frozenset({"ALL_OF", "ANY_OF"})
SKILL_KINDS = frozenset({
    "SKILL_AT_LEAST",
    "SKILL_SUM_AT_LEAST",
})
VALID_BOOSTABILITY = frozenset({"YES", "NO", "UNKNOWN"})
VALID_TIMING = frozenset({"YES", "NO", "UNKNOWN"})


@dataclass(frozen=True)
class RequirementNode:
    """A requirement, unresolved route, or logical combination."""

    kind: str
    skill: str | None = None
    skills: tuple[str, ...] = ()
    minimum: int | None = None
    boostable: str = "UNKNOWN"
    children: tuple["RequirementNode", ...] = ()
    description: str | None = None

    def __post_init__(self):
        valid_kinds = (
            GROUP_KINDS
            | SKILL_KINDS
            | {"UNRESOLVED_ROUTE"}
        )

        if self.kind not in valid_kinds:
            raise ValueError(
                f"Unknown requirement kind: {self.kind!r}"
            )

        if self.boostable not in VALID_BOOSTABILITY:
            raise ValueError("Invalid boostability value.")

        if type(self.skills) is not tuple:
            raise TypeError("Skills must be a tuple.")

        if type(self.children) is not tuple:
            raise TypeError("Children must be a tuple.")

        if self.kind in GROUP_KINDS:
            if len(self.children) < 2:
                raise ValueError(
                    "Logical groups need at least two children."
                )

            if not all(
                isinstance(child, RequirementNode)
                for child in self.children
            ):
                raise TypeError(
                    "Logical group children must be requirements."
                )

            if (
                self.skill is not None
                or self.skills
                or self.minimum is not None
                or self.description is not None
                or self.boostable != "UNKNOWN"
            ):
                raise ValueError(
                    "Logical groups cannot contain leaf fields."
                )

        elif self.kind == "SKILL_AT_LEAST":
            if self.skill not in SKILLS:
                raise ValueError(
                    f"Unknown skill: {self.skill!r}"
                )

            self._validate_minimum()

            if (
                self.skills
                or self.children
                or self.description is not None
            ):
                raise ValueError(
                    "Individual skill has unexpected fields."
                )

        elif self.kind == "SKILL_SUM_AT_LEAST":
            if (
                len(self.skills) < 2
                or len(self.skills) != len(set(self.skills))
                or any(skill not in SKILLS for skill in self.skills)
            ):
                raise ValueError(
                    "Combined skill list is invalid."
                )

            self._validate_minimum()

            if (
                self.skill is not None
                or self.children
                or self.description is not None
            ):
                raise ValueError(
                    "Combined skill has unexpected fields."
                )

        elif self.kind == "UNRESOLVED_ROUTE":
            if (
                not isinstance(self.description, str)
                or not self.description.strip()
            ):
                raise ValueError(
                    "Unresolved routes require a description."
                )

            if (
                self.skill is not None
                or self.skills
                or self.minimum is not None
                or self.children
                or self.boostable != "UNKNOWN"
            ):
                raise ValueError(
                    "Unresolved route has unexpected fields."
                )

    def _validate_minimum(self):
        if (
            type(self.minimum) is not int
            or self.minimum < 1
        ):
            raise ValueError(
                "Minimum must be a positive integer."
            )

    def to_dict(self):
        """Return a JSON-compatible representation."""
        result = {"kind": self.kind}

        if self.kind in GROUP_KINDS:
            result["children"] = [
                child.to_dict()
                for child in self.children
            ]

        elif self.kind == "SKILL_AT_LEAST":
            result.update({
                "skill": self.skill,
                "minimum": self.minimum,
                "boostable": self.boostable,
            })

        elif self.kind == "SKILL_SUM_AT_LEAST":
            result.update({
                "skills": list(self.skills),
                "minimum": self.minimum,
                "boostable": self.boostable,
            })

        else:
            result["description"] = self.description

        return result


@dataclass(frozen=True)
class RequirementObservation:
    """An unverified expression tied to an exact Wiki source."""

    source_quest_id: str
    wiki_revision: int
    line_number: int
    source_text: str
    expression: RequirementNode
    required_to_start: str = "UNKNOWN"
    verification_status: str = field(
        default="UNVERIFIED",
        init=False,
    )

    def __post_init__(self):
        if (
            not isinstance(self.source_quest_id, str)
            or not re.fullmatch(
                r"[a-z][a-z0-9_]*",
                self.source_quest_id,
            )
        ):
            raise ValueError("Invalid source quest ID.")

        if (
            type(self.wiki_revision) is not int
            or self.wiki_revision < 1
        ):
            raise ValueError("Invalid Wiki revision.")

        if (
            type(self.line_number) is not int
            or self.line_number < 1
        ):
            raise ValueError("Invalid source line number.")

        if (
            not isinstance(self.source_text, str)
            or not self.source_text.strip()
        ):
            raise ValueError("Source text is required.")

        if not isinstance(self.expression, RequirementNode):
            raise TypeError("Expression must be a RequirementNode.")

        if self.required_to_start not in VALID_TIMING:
            raise ValueError("Invalid quest-start timing.")

    def to_dict(self):
        """Retain provenance and uncertainty for later review."""
        return {
            "source_quest_id": self.source_quest_id,
            "wiki_revision": self.wiki_revision,
            "line_number": self.line_number,
            "source_text": self.source_text,
            "required_to_start": self.required_to_start,
            "verification_status": self.verification_status,
            "expression": self.expression.to_dict(),
        }
