"""Validate verified, zero-additional-skill OSRS bypasses.

Original frozen requirements remain unchanged. This module derives
a separate set of effective skill requirements for eligibility.

Only independently reviewed BYPASSABLE requirements with a verified
route requiring no additional skill thresholds are supported.
More complex OR routes require separate modelling.
"""

from collections.abc import Mapping
from hashlib import sha256


class VerifiedBypassError(ValueError):
    """The submitted bypass is not supported by frozen evidence."""


def effective_skills_with_verified_bypasses(proposal, review):
    """Return effective skills, boostability and bypassed skill IDs.

    A bypass needs exact frozen-source identity, a documented route,
    evidence references and a resolved matching review finding.

    Evidence references are audit metadata; independent review and
    organiser approval remain separate requirements.
    """
    if not isinstance(proposal, Mapping) or not isinstance(review, Mapping):
        raise VerifiedBypassError("Proposal and review must be mappings")

    observations = proposal.get("observations")

    if not isinstance(observations, Mapping):
        raise VerifiedBypassError("Missing frozen observations")

    skills = observations.get("skills")
    entries = [] if skills is None else skills.get("skills")

    if not isinstance(entries, list):
        raise VerifiedBypassError("Invalid frozen skill observations")

    source_text = proposal.get("requirements_wikitext")
    lines = (
        source_text.splitlines()
        if isinstance(source_text, str)
        else []
    )

    source_levels = {}
    source_boostability = {}

    for entry in entries:
        if not isinstance(entry, Mapping):
            raise VerifiedBypassError("Invalid frozen skill entry")

        skill = entry.get("skill")
        level = entry.get("level")
        boostability = entry.get("boostable")
        line = entry.get("line_number")

        if not (
            isinstance(skill, str)
            and bool(skill)
            and skill not in source_levels
            and type(level) is int
            and level > 0
            and boostability in ("yes", "no", "unknown")
            and type(line) is int
            and 1 <= line <= len(lines)
            and entry.get("source_text") == lines[line - 1]
        ):
            raise VerifiedBypassError("Frozen skill identity mismatch")

        source_levels[skill] = level
        source_boostability[skill] = boostability

    exceptions = review.get("verified_bypass_exceptions", [])

    if not isinstance(exceptions, list):
        raise VerifiedBypassError("Bypass exceptions must be a list")

    conditional_lines = (
        [] if skills is None
        else skills.get("conditional_skill_lines")
    )

    if not isinstance(conditional_lines, list):
        raise VerifiedBypassError("Invalid frozen conditional observations")

    evidence = review.get("reviewer_evidence_refs", [])
    findings = review.get("review_findings", [])

    if not isinstance(evidence, list) or not isinstance(findings, list):
        raise VerifiedBypassError("Missing review evidence or findings")

    required_keys = {
        "quest_id",
        "skill",
        "source_level",
        "source_boostability",
        "source_line",
        "source_text",
        "source_wikitext_sha256",
        "wiki_revision",
        "verification_decision",
        "alternative_route",
        "alternative_skill_requirements",
        "non_skill_conditions",
        "evidence_refs",
    }

    omitted = set()

    for exception in exceptions:
        if not isinstance(exception, dict) or set(exception) != required_keys:
            raise VerifiedBypassError(
                "Unexpected bypass exception structure"
            )

        source_digest = (
            sha256(source_text.encode("utf-8")).hexdigest()
            if isinstance(source_text, str)
            else None
        )

        if (
            not isinstance(
                exception["source_wikitext_sha256"], str
            )
            or exception["source_wikitext_sha256"]
                != source_digest
        ):
            raise VerifiedBypassError(
                "Full frozen requirements text mismatch"
            )

        skill = exception["skill"]

        if (
            not isinstance(skill, str)
            or skill not in source_levels
            or skill in omitted
        ):
            raise VerifiedBypassError(
                "Unknown or duplicate bypass skill"
            )

        entry = next(
            item for item in entries
            if item["skill"] == skill
        )

        line = entry["line_number"]

        if not (
            exception["quest_id"] == proposal.get("quest_id")
            and type(exception["wiki_revision"]) is int
            and exception["wiki_revision"]
                == proposal.get("wiki_revision")
            and type(exception["source_line"]) is int
            and exception["source_line"] == line
            and type(exception["source_level"]) is int
            and exception["source_level"] == entry["level"]
            and exception["source_boostability"]
                == entry["boostable"]
            and exception["source_text"] == lines[line - 1]
        ):
            raise VerifiedBypassError("Bypass source identity mismatch")

        corresponding = [
            item
            for item in conditional_lines
            if item.get("line_number") == line
            and item.get("source_text") == lines[line - 1]
            and item.get("condition_kind") == "BYPASSABLE"
            and item.get("needs_review") is True
        ]

        if not (
            proposal.get("requirements_status") == "FIELD_PRESENT"
            and entry.get("condition_kind") == "BYPASSABLE"
            and entry.get("needs_condition_review") is True
            and len(corresponding) == 1
            and "bypass" in lines[line - 1].casefold()
        ):
            raise VerifiedBypassError(
                "Not a frozen bypassable skill"
            )

        if (
            exception["verification_decision"]
            != "VERIFIED_ACCESSIBLE_BYPASS"
        ):
            raise VerifiedBypassError(
                "Bypass route not verified"
            )

        route = exception["alternative_route"]
        conditions = exception["non_skill_conditions"]
        refs = exception["evidence_refs"]

        if not (
            isinstance(route, str)
            and bool(route.strip())
            and exception["alternative_skill_requirements"] == {}
            and isinstance(conditions, list)
            and all(
                isinstance(condition, str)
                and bool(condition.strip())
                for condition in conditions
            )
            and isinstance(refs, list)
            and bool(refs)
            and all(
                isinstance(ref, str)
                and ref.startswith(
                    "https://oldschool.runescape.wiki/w/"
                )
                and ref in evidence
                for ref in refs
            )
            and len(refs) == len(set(refs))
        ):
            raise VerifiedBypassError(
                "Alternative route evidence incomplete"
            )

        matching_findings = [
            item
            for item in findings
            if isinstance(item, Mapping)
            and item.get("code") == "VERIFIED_ACCESSIBLE_BYPASS"
            and item.get("source_line") == line
            and item.get("status") == "RESOLVED"
            and isinstance(item.get("resolution"), str)
            and bool(item["resolution"].strip())
            and isinstance(
                item.get("resolution_evidence_refs"), list
            )
            and all(
                ref in item["resolution_evidence_refs"]
                for ref in refs
            )
        ]

        if len(matching_findings) != 1:
            raise VerifiedBypassError(
                "Missing resolved bypass review finding"
            )

        omitted.add(skill)

    effective_skills = {
        skill: level
        for skill, level in source_levels.items()
        if skill not in omitted
    }

    effective_boostability = {
        skill: value
        for skill, value in source_boostability.items()
        if skill not in omitted
    }

    return (
        effective_skills,
        effective_boostability,
        tuple(sorted(omitted)),
    )
