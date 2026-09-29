from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from utils.board_generation import TileCandidate


@dataclass(frozen=True)
class CandidateConflict:
    tag: str
    candidate_titles: tuple[str, ...]


@dataclass(frozen=True)
class CandidateRequirementSummary:
    title: str
    point_value: int
    primary_category: str
    hard_unique_tags: tuple[str, ...]
    effective_skill_requirements: dict[str, int]
    recommended_skill_requirements: dict[str, int]
    access_flags: tuple[str, ...]


@dataclass(frozen=True)
class CatalogueSummary:
    candidate_count: int
    counts_by_point_value: dict[int, int]
    counts_by_primary_category: dict[str, int]
    requirement_summaries: tuple[CandidateRequirementSummary, ...]
    conflicts: tuple[CandidateConflict, ...]


def build_candidate_requirement_summary(candidate):
    return CandidateRequirementSummary(
        title=candidate.title,
        point_value=candidate.point_value,
        primary_category=candidate.primary_category.value,
        hard_unique_tags=tuple(
            sorted(
                candidate.all_hard_unique_tags
            )
        ),
        effective_skill_requirements=dict(
            candidate.access_profile.effective_skill_requirements
        ),
        recommended_skill_requirements=dict(
            candidate.access_profile.recommended_skill_requirements
        ),
        access_flags=tuple(
            sorted(
                flag.value
                for flag in candidate.access_profile.access_flags
            )
        ),
    )


def find_candidate_conflicts(candidates):
    titles_by_tag = defaultdict(list)

    for candidate in candidates:
        for tag in candidate.all_hard_unique_tags:
            titles_by_tag[tag].append(
                candidate.title
            )

    return tuple(
        CandidateConflict(
            tag=tag,
            candidate_titles=tuple(
                sorted(
                    titles
                )
            ),
        )
        for tag, titles in sorted(
            titles_by_tag.items()
        )
        if len(titles) > 1
    )


def build_catalogue_summary(candidates):
    candidates = tuple(
        candidates
    )

    return CatalogueSummary(
        candidate_count=len(
            candidates
        ),
        counts_by_point_value=dict(
            Counter(
                candidate.point_value
                for candidate in candidates
            )
        ),
        counts_by_primary_category=dict(
            Counter(
                candidate.primary_category.value
                for candidate in candidates
            )
        ),
        requirement_summaries=tuple(
            build_candidate_requirement_summary(
                candidate
            )
            for candidate in candidates
        ),
        conflicts=find_candidate_conflicts(
            candidates
        ),
    )


def format_count_map(counts):
    if not counts:
        return "None"

    return ", ".join(
        f"{key}: {value}"
        for key, value in sorted(
            counts.items(),
            key=lambda item: str(item[0])
        )
    )


def format_skill_requirements(requirements):
    if not requirements:
        return "None"

    return ", ".join(
        f"{skill_id.replace('_', ' ').title()} {level}"
        for skill_id, level in sorted(
            requirements.items()
        )
    )


def format_sequence(values):
    if not values:
        return "None"

    return ", ".join(
        values
    )


def format_point_label(point_value):
    return "pt" if point_value == 1 else "pts"


def format_candidate_requirement_summary(summary):
    return "\n".join(
        (
            (
                f"{summary.title} "
                f"({summary.point_value} {format_point_label(summary.point_value)}, "
                f"{summary.primary_category})"
            ),
            f"  Tags: {format_sequence(summary.hard_unique_tags)}",
            (
                "  Effective skills: "
                f"{format_skill_requirements(summary.effective_skill_requirements)}"
            ),
            (
                "  Recommended skills: "
                f"{format_skill_requirements(summary.recommended_skill_requirements)}"
            ),
            f"  Access flags: {format_sequence(summary.access_flags)}",
        )
    )


def format_candidate_conflict(conflict):
    return (
        f"{conflict.tag}: "
        + " | ".join(
            conflict.candidate_titles
        )
    )


def format_catalogue_summary(summary):
    lines = [
        f"Candidate count: {summary.candidate_count}",
        f"By point value: {format_count_map(summary.counts_by_point_value)}",
        f"By primary category: {format_count_map(summary.counts_by_primary_category)}",
        "",
        "Candidates:",
    ]

    for candidate_summary in summary.requirement_summaries:
        lines.append(
            format_candidate_requirement_summary(
                candidate_summary
            )
        )

    lines.extend(
        [
            "",
            "Conflicts:",
        ]
    )

    if summary.conflicts:
        for conflict in summary.conflicts:
            lines.append(
                format_candidate_conflict(
                    conflict
                )
            )
    else:
        lines.append(
            "None"
        )

    return "\n".join(
        lines
    )

