"""Validate OSRS requirements reviews against their proposals.

Validation does not approve requirements or establish eligibility.
Pending and approved reviews must remain non-activated.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from utils.osrs_quest_data import (
    get_curated_quest_requirements,
)
from utils.osrs_verified_bypass import (
    VerifiedBypassError,
    effective_skills_with_verified_bypasses,
)
from utils.osrs_verified_exceptional_routes import (
    VerifiedExceptionalRouteError,
    effective_verified_exceptional_requirement,
)
from utils.osrs_quest_requirements import (
    QuestUnmeasuredCondition,
)


PROPOSALS_PATH = Path(
    "data/osrs_requirement_proposals_v1.json"
)

REVIEWS_PATH = Path(
    "data/osrs_requirement_reviews_v1.json"
)


def read_json(path):
    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )



# Explicitly scoped, source-locked quest-template exceptions.
# These are not approvals or activations.
VERIFIED_QUEST_TEMPLATE_SCOPE = frozenset({
    ("troll_stronghold", 15326717, 1, "death_plateau"),
    (
        "horror_from_the_deep",
        15375082,
        2,
        "miniquest_alfred_grimhands_barcrawl",
    ),
    (
        "icthlarins_little_helper",
        15365541,
        1,
        "gertrudes_cat",
    ),
})


def verified_non_numeric_quest_templates(
    proposal, review, curated_ids
):
    """Recognise only source-locked, verified quest-template warnings."""
    exceptions = review.get("verified_quest_template_exceptions")

    if exceptions is None:
        return frozenset()

    if not isinstance(exceptions, list) or not exceptions:
        raise ValueError("Invalid quest-template exception list")

    source = proposal.get("requirements_wikitext")
    observations = proposal.get("observations")

    if (
        proposal.get("requirements_status") != "FIELD_PRESENT"
        or not isinstance(source, str)
        or not isinstance(observations, dict)
    ):
        raise ValueError("Quest-template source is unavailable")

    skills = observations.get("skills")
    prerequisites = observations.get("prerequisites")

    if not isinstance(skills, dict) or not isinstance(
        prerequisites, dict
    ):
        raise ValueError("Quest-template observations unavailable")

    warnings = skills.get("review_items")
    candidates = prerequisites.get("direct_candidates")
    findings = review.get("review_findings")
    reviewer_refs = review.get("reviewer_evidence_refs")

    if not all(
        isinstance(value, list)
        for value in (
            warnings, candidates, findings, reviewer_refs
        )
    ):
        raise ValueError("Invalid quest-template review evidence")

    required_keys = {
        "quest_id",
        "wiki_revision",
        "source_line",
        "source_text",
        "source_wikitext_sha256",
        "parser_warning_type",
        "prerequisite_quest_id",
        "verification_decision",
        "evidence_refs",
    }

    source_lines = source.splitlines()
    source_digest = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()

    recognised = set()

    for exception in exceptions:
        if (
            not isinstance(exception, dict)
            or set(exception) != required_keys
        ):
            raise ValueError("Unexpected quest-template exception structure")

        line = exception["source_line"]
        prerequisite_id = exception["prerequisite_quest_id"]

        if (
            type(line) is not int
            or not (1 <= line <= len(source_lines))
            or type(exception["wiki_revision"]) is not int
        ):
            raise ValueError("Invalid quest-template source identity")

        scope = (
            exception["quest_id"],
            exception["wiki_revision"],
            line,
            prerequisite_id,
        )

        if (
            scope not in VERIFIED_QUEST_TEMPLATE_SCOPE
            or exception["quest_id"] != proposal.get("quest_id")
            or exception["wiki_revision"]
            != proposal.get("wiki_revision")
            or exception["wiki_revision"]
            != review.get("wiki_revision")
            or exception["source_text"] != source_lines[line - 1]
            or exception["source_wikitext_sha256"] != source_digest
            or exception["parser_warning_type"] != "NON_NUMERIC_SCP"
            or exception["verification_decision"]
            != "VERIFIED_DIRECT_QUEST_PREREQUISITE"
            or source_lines[line - 1].count("{{SCP|Quest}}") != 1
        ):
            raise ValueError("Unverified quest-template source identity")

        matching_warnings = [
            item for item in warnings
            if isinstance(item, dict)
            and item.get("line_number") == line
        ]

        if (
            len(matching_warnings) != 1
            or matching_warnings[0].get("type")
            != "NON_NUMERIC_SCP"
            or matching_warnings[0].get("source_text")
            != source_lines[line - 1]
        ):
            raise ValueError("Quest-template parser warning mismatch")

        matching_candidates = [
            item for item in candidates
            if isinstance(item, dict)
            and item.get("line_number") == line
            and item.get("source_text") == source_lines[line - 1]
            and item.get("target_quest_id") == prerequisite_id
        ]

        if (
            len(matching_candidates) != 1
            or prerequisite_id not in curated_ids
            or prerequisite_id not in review.get(
                "proposed_direct_prerequisite_quest_ids", []
            )
        ):
            raise ValueError("Quest-template prerequisite mismatch")

        refs = exception["evidence_refs"]

        if (
            not isinstance(refs, list)
            or not refs
            or not all(
                isinstance(ref, str)
                and ref.startswith(
                    "https://oldschool.runescape.wiki/w/"
                )
                and ref in reviewer_refs
                for ref in refs
            )
        ):
            raise ValueError("Missing quest-template evidence")

        if len(refs) != len(set(refs)):
            raise ValueError("Duplicate quest-template evidence")

        matching_findings = [
            finding for finding in findings
            if isinstance(finding, dict)
            and finding.get("code")
            == "VERIFIED_QUEST_TEMPLATE_PREREQUISITE"
            and finding.get("source_line") == line
            and finding.get("status") == "RESOLVED"
            and isinstance(finding.get("resolution"), str)
            and bool(finding["resolution"].strip())
            and finding.get("resolution_evidence_refs") == refs
        ]

        if len(matching_findings) != 1:
            raise ValueError("Missing resolved quest-template finding")

        warning_key = (
            "NON_NUMERIC_SCP",
            line,
            source_lines[line - 1],
        )

        if warning_key in recognised:
            raise ValueError("Duplicate quest-template exception")

        recognised.add(warning_key)

    return frozenset(recognised)



# Only these four frozen conditional skill annotations are
# eligible for this exception mechanism. The source text,
# mandatory level and boostability must match exactly.
VERIFIED_CONDITIONAL_SKILL_SCOPE = {
    (
        "tai_bwo_wannai_trio",
        15376159,
        1,
        "agility",
        15,
        "yes",
        "COMMENT_ONLY",
    ): {
        "annotation_kind": "COMMENT_ONLY_RECOMMENDATION",
        "source_text": (
            "* <!--DO NOT ADD 30 FIREMAKING, IT IS ONLY "
            "RECOMMENDED AND ALTERNATIVES ARE MENTIONED "
            "ON THIS PAGE-->{{SCP|Agility|15|link=yes}} "
            "{{Boostable|Yes}} {{Questreqstart|no}}"
        ),
        "verified_interpretation": (
            "15 Agility remains mandatory and boostable. "
            "30 Firemaking is recommended only and is not "
            "a mandatory skill requirement."
        ),
        "wiki_ref": (
            "https://oldschool.runescape.wiki/w/"
            "Tai_Bwo_Wannai_Trio"
        ),
        "needs_review": False,
    },
    (
        "tai_bwo_wannai_trio",
        15376159,
        3,
        "fishing",
        5,
        "yes",
        "CONTEXTUAL_REVIEW",
    ): {
        "annotation_kind": "OPTIONAL_PERSONAL_CATCH",
        "source_text": (
            "* {{SCP|Fishing|5|link=yes}} "
            "{{Boostable|Yes}} {{Questreqstart|no}} "
            "<ref>Level 65 is required if you wish to catch "
            "the [[Raw karambwan]] yourself.</ref>"
            "<!--Do not add 30 Firemaking-->"
        ),
        "verified_interpretation": (
            "5 Fishing remains mandatory and boostable. "
            "65 Fishing is required only when personally "
            "catching raw karambwan. Obtaining or replacing "
            "the item may impose practical restrictions, "
            "especially for restricted accounts."
        ),
        "wiki_ref": (
            "https://oldschool.runescape.wiki/w/"
            "Tai_Bwo_Wannai_Trio"
        ),
        "needs_review": True,
    },
    (
        "troll_stronghold",
        15326717,
        2,
        "agility",
        15,
        "yes",
        "CONTEXTUAL_REVIEW",
    ): {
        "annotation_kind": "RECOMMENDED_AGILITY",
        "source_text": (
            "* {{SCP|Agility|15|link=yes}} "
            "{{Boostable|yes}} {{Questreqstart|no}} "
            "(47 is recommended)"
        ),
        "verified_interpretation": (
            "15 Agility remains mandatory and boostable. "
            "47 Agility is recommended only and must not "
            "replace the mandatory threshold."
        ),
        "wiki_ref": (
            "https://oldschool.runescape.wiki/w/"
            "Troll_Stronghold"
        ),
        "needs_review": True,
    },
    (
        "tears_of_guthix",
        15292296,
        3,
        "crafting",
        20,
        "yes",
        "CONTEXTUAL_REVIEW",
    ): {
        "annotation_kind": "ROUTE_SPECIFIC_BOOSTABILITY",
        "source_text": (
            "* {{SCP|Crafting|20|link=yes}} "
            "{{Boostable|yes}} {{Questreqstart|no}} "
            "<ref>Adding the sapphire lens to a "
            "[[Bullseye lantern (unf)]] is boostable. "
            "Adding it to a [[Bullseye lantern (empty)]] "
            "or [[Bullseye lantern]] is not boostable.</ref>"
        ),
        "verified_interpretation": (
            "20 Crafting remains mandatory. Boosting is "
            "valid when adding the sapphire lens to a "
            "bullseye lantern (unf). Adding the lens to "
            "a bullseye lantern (empty) or a completed "
            "bullseye lantern is not boostable. The "
            "route-specific item restriction remains "
            "documented and must not be generalised."
        ),
        "wiki_ref": (
            "https://oldschool.runescape.wiki/w/"
            "Tears_of_Guthix"
        ),
        "needs_review": True,
    },
}


def verified_conditional_skill_annotations(proposal, review):
    """Recognise only explicitly scoped, evidenced annotations."""
    exceptions = review.get(
        "verified_conditional_skill_annotations"
    )

    if exceptions is None:
        return frozenset()

    if not isinstance(exceptions, list) or not exceptions:
        raise ValueError("Invalid conditional skill exception list")

    source = proposal.get("requirements_wikitext")
    observations = proposal.get("observations")

    if (
        proposal.get("requirements_status") != "FIELD_PRESENT"
        or not isinstance(source, str)
        or not isinstance(observations, dict)
    ):
        raise ValueError("Conditional skill source unavailable")

    skills = observations.get("skills")

    if not isinstance(skills, dict):
        raise ValueError("Conditional skill observations unavailable")

    skill_items = skills.get("skills")
    conditional_items = skills.get("conditional_skill_lines")
    findings = review.get("review_findings")
    reviewer_refs = review.get("reviewer_evidence_refs")

    if not all(
        isinstance(value, list)
        for value in (
            skill_items,
            conditional_items,
            findings,
            reviewer_refs,
        )
    ):
        raise ValueError("Invalid conditional skill review structure")

    required_keys = {
        "quest_id",
        "wiki_revision",
        "source_line",
        "source_text",
        "source_wikitext_sha256",
        "skill",
        "source_level",
        "source_boostability",
        "condition_kind",
        "annotation_kind",
        "verified_interpretation",
        "verification_decision",
        "evidence_refs",
    }

    source_lines = source.splitlines()
    source_digest = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()

    recognised = set()

    for exception in exceptions:
        if (
            not isinstance(exception, dict)
            or set(exception) != required_keys
        ):
            raise ValueError(
                "Unexpected conditional skill exception structure"
            )

        line = exception["source_line"]
        level = exception["source_level"]
        revision = exception["wiki_revision"]

        if (
            type(line) is not int
            or type(level) is not int
            or type(revision) is not int
            or not (1 <= line <= len(source_lines))
        ):
            raise ValueError("Invalid conditional skill source identity")

        scope = (
            exception["quest_id"],
            revision,
            line,
            exception["skill"],
            level,
            exception["source_boostability"],
            exception["condition_kind"],
        )

        rule = VERIFIED_CONDITIONAL_SKILL_SCOPE.get(scope)

        if rule is None:
            raise ValueError(
                "Unsupported conditional skill annotation"
            )

        source_line = source_lines[line - 1]

        if (
            exception["quest_id"] != proposal.get("quest_id")
            or revision != proposal.get("wiki_revision")
            or revision != review.get("wiki_revision")
            or source_line != rule["source_text"]
            or exception["source_text"] != source_line
            or exception["source_wikitext_sha256"]
            != source_digest
            or exception["annotation_kind"]
            != rule["annotation_kind"]
            or exception["verified_interpretation"]
            != rule["verified_interpretation"]
            or exception["verification_decision"]
            != "VERIFIED_CONDITIONAL_SKILL_ANNOTATION"
        ):
            raise ValueError(
                "Unverified conditional skill source identity"
            )

        matching_skills = [
            item for item in skill_items
            if isinstance(item, dict)
            and item.get("skill") == exception["skill"]
            and item.get("level") == level
            and item.get("boostable")
            == exception["source_boostability"]
            and item.get("condition_kind")
            == exception["condition_kind"]
            and item.get("line_number") == line
            and item.get("source_text") == source_line
            and item.get("needs_condition_review")
            is rule["needs_review"]
        ]

        matching_conditions = [
            item for item in conditional_items
            if isinstance(item, dict)
            and item.get("line_number") == line
            and item.get("source_text") == source_line
            and item.get("condition_kind")
            == exception["condition_kind"]
            and item.get("needs_review")
            is rule["needs_review"]
        ]

        if (
            len(matching_skills) != 1
            or len(matching_conditions) != 1
            or review.get(
                "proposed_direct_skill_requirements", {}
            ).get(exception["skill"]) != level
        ):
            raise ValueError(
                "Conditional skill observation mismatch"
            )

        refs = exception["evidence_refs"]
        page_ref = rule["wiki_ref"]

        if (
            not isinstance(refs, list)
            or not refs
            or len(refs) != len(set(refs))
            or page_ref not in refs
            or not all(
                isinstance(ref, str)
                and ref.startswith(
                    "https://oldschool.runescape.wiki/w/"
                )
                and ref in reviewer_refs
                for ref in refs
            )
        ):
            raise ValueError(
                "Missing conditional skill evidence"
            )

        matching_findings = [
            finding for finding in findings
            if isinstance(finding, dict)
            and finding.get("code")
            == "VERIFIED_CONDITIONAL_SKILL_ANNOTATION"
            and finding.get("source_line") == line
            and finding.get("status") == "RESOLVED"
            and isinstance(
                finding.get("resolution"), str
            )
            and bool(finding["resolution"].strip())
            and finding.get(
                "resolution_evidence_refs"
            ) == refs
        ]

        source_findings = [
            finding for finding in findings
            if isinstance(finding, dict)
            and finding.get("code")
            == "INDEPENDENT_SOURCE_VERIFICATION"
            and finding.get("status") == "RESOLVED"
            and page_ref in finding.get(
                "resolution_evidence_refs", []
            )
        ]

        if (
            len(matching_findings) != 1
            or len(source_findings) != 1
        ):
            raise ValueError(
                "Missing resolved conditional skill verification"
            )

        identity = (
            exception["skill"],
            line,
            source_line,
        )

        if identity in recognised:
            raise ValueError(
                "Duplicate conditional skill annotation"
            )

        recognised.add(identity)

    return frozenset(recognised)


def verified_quest_point_assumption(review, quest_points):
    """Verify an explicitly authorised Quest Point eligibility assumption.

    Quest Point totals are not measured by ClanBeacon. This policy
    does not waive skills, prerequisite quests or conditional rules.
    """
    assumption = review.get("quest_point_assumption")

    if not quest_points:
        return assumption is None

    if not isinstance(assumption, dict):
        return False

    expected_requirements = [
        {
            "level": item["level"],
            "source_line": item["line_number"],
            "source_text": item["source_text"],
            "required_to_start": item["required_to_start"],
        }
        for item in quest_points
    ]

    evidence_refs = assumption.get("independent_evidence_refs")

    return (
        assumption.get("policy") == "ASSUME_QUEST_POINTS_MET"
        and assumption.get("decision")
        == "ASSUMED_NOT_INDEPENDENTLY_VERIFIED"
        and assumption.get("authorised_by")
        == "CLANBEACON_ORGANISER_STEP_267_16"
        and assumption.get("wiki_revision") == review["wiki_revision"]
        and assumption.get("source_requirements")
        == expected_requirements
        and isinstance(assumption.get("policy_notes"), str)
        and bool(assumption["policy_notes"].strip())
        and isinstance(evidence_refs, list)
        and bool(evidence_refs)
        and evidence_refs == review.get("reviewer_evidence_refs")
        and all(
            isinstance(ref, str) and ref.strip()
            for ref in evidence_refs
        )
        and any(
            ref.startswith("https://oldschool.runescape.wiki/w/")
            for ref in evidence_refs
        )
        and all(
            type(item["level"]) is int
            and item["level"] > 0
            and item["required_to_start"] == "yes"
            and item["condition_kind"] == "NONE_DETECTED"
            and item["needs_condition_review"] is False
            and type(item["line_number"]) is int
            for item in quest_points
        )
    )

def validate_reviews():
    proposal_data = read_json(PROPOSALS_PATH)
    review_data = read_json(REVIEWS_PATH)

    if (
        proposal_data.get("schema_version") != 1
        or proposal_data.get("purpose") != "REVIEW_ONLY"
    ):
        raise ValueError("Invalid proposals schema.")

    if (
        review_data.get("schema_version") != 1
        or review_data.get("purpose")
        != "MANUAL_REQUIREMENTS_REVIEW"
    ):
        raise ValueError("Invalid reviews schema.")

    proposals = proposal_data.get("proposals")
    reviews = review_data.get("reviews")

    if not isinstance(proposals, list) or len(proposals) != 214:
        raise ValueError("Expected 214 proposals.")

    if not isinstance(reviews, list):
        raise ValueError("Reviews must be a list.")

    proposal_lookup = {}

    for proposal in proposals:
        quest_id = proposal["quest_id"]

        if quest_id in proposal_lookup:
            raise ValueError(
                f"Duplicate proposal: {quest_id}"
            )

        proposal_lookup[quest_id] = proposal

    curated_lookup = {
        quest.quest_id: quest
        for quest in get_curated_quest_requirements()
    }
    curated_ids = set(curated_lookup)

    seen_reviews = set()
    results = []

    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("Review must be an object.")

        quest_id = review.get("quest_id")

        if quest_id not in proposal_lookup:
            raise ValueError(
                f"Unknown reviewed quest: {quest_id}"
            )

        if quest_id in seen_reviews:
            raise ValueError(
                f"Duplicate review: {quest_id}"
            )

        seen_reviews.add(quest_id)

        proposal = proposal_lookup[quest_id]

        if (
            proposal["approval_status"] != "UNVERIFIED"
            or proposal["eligibility_status"] != "NOT_EVALUATED"
        ):
            raise ValueError(
                f"Unexpected proposal state: {quest_id}"
            )

        if (
            type(review.get("wiki_revision")) is not int
            or review["wiki_revision"]
            != proposal["wiki_revision"]
        ):
            raise ValueError(
                f"Source revision mismatch: {quest_id}"
            )

        review_status = review.get("review_status")

        if review_status not in ("PENDING", "APPROVED"):
            raise ValueError(
                f"Unsupported review decision: {quest_id}"
            )

        activation_status = review.get("activation_status")

        if activation_status not in (
            "NOT_ACTIVATED",
            "ACTIVATED",
        ):
            raise ValueError(
                f"Invalid activation status: {quest_id}"
            )

        if type(review.get("existing_curated_record")) is not bool:
            raise ValueError(
                f"Invalid original curated-record status: {quest_id}"
            )

        if (
            activation_status == "NOT_ACTIVATED"
            and review["existing_curated_record"]
            != (quest_id in curated_ids)
        ):
            raise ValueError(
                f"Curated-record mismatch: {quest_id}"
            )

        observations = proposal["observations"]

        skills = observations["skills"]
        prerequisites = observations["prerequisites"]

        if skills is None:
            expected_skills = {}
        else:
            skill_items = skills["skills"]

            # A simple mapping cannot safely represent multiple
            # conditional requirements for the same skill.
            if len({
                item["skill"]
                for item in skill_items
            }) != len(skill_items):
                raise ValueError(
                    f"Repeated skill requires detailed review: {quest_id}"
                )

            expected_skills = {
                item["skill"]: item["level"]
                for item in skill_items
            }

        if prerequisites is None:
            expected_prerequisites = []
        else:
            expected_prerequisites = [
                item["target_quest_id"]
                for item in prerequisites["direct_candidates"]
            ]

        # Validate exceptional requirements for ALL reviews,
        # including pending reviews. Merely documenting an
        # exception must not approve or activate a quest.
        exceptional_requirement = None

        if "verified_exceptional_requirement" in review:
            if (
                "verified_bypass_exceptions" in review
                or "verified_conditional_skill_annotations"
                in review
            ):
                raise ValueError(
                    f"Conflicting exceptional requirement "
                    f"metadata: {quest_id}"
                )

            try:
                exceptional_requirement = (
                    effective_verified_exceptional_requirement(
                        proposal, review
                    )
                )
            except VerifiedExceptionalRouteError as error:
                raise ValueError(
                    f"Invalid exceptional requirement: "
                    f"{quest_id}: {error}"
                ) from error

            if exceptional_requirement is None:
                raise ValueError(
                    f"Empty exceptional requirement: {quest_id}"
                )

        # Keep frozen source skills separate from effective
        # eligibility when a verified bypass is supplied.
        if "verified_bypass_exceptions" in review:
            try:
                (
                    effective_skills,
                    effective_boostability,
                    bypassed_skills,
                ) = effective_skills_with_verified_bypasses(
                    proposal, review
                )
            except VerifiedBypassError as error:
                raise ValueError(
                    f"Invalid verified bypass exception: {quest_id}: "
                    f"{error}"
                ) from error

            if not bypassed_skills:
                raise ValueError(
                    f"Empty verified bypass exception: {quest_id}"
                )
        else:
            effective_skills = expected_skills
            effective_boostability = {
                item["skill"]: item["boostable"]
                for item in (
                    [] if skills is None else skills["skills"]
                )
            }
            bypassed_skills = ()

        # Verified exceptional requirements are validated above
        # for all review states. Their effective direct skills
        # are distinct from the immutable Wiki observations.
        #
        # A substituted numerical route is never an
        # unconditional waiver: its corresponding non-skill
        # condition must also be preserved during activation.
        if exceptional_requirement is not None:
            effective_skills = dict(
                exceptional_requirement[
                    "effective_direct_skill_requirements"
                ]
            )
            effective_boostability = dict(
                exceptional_requirement[
                    "effective_direct_skill_boostability"
                ]
            )

            if set(effective_skills) != set(effective_boostability):
                raise ValueError(
                    f"Exceptional skill/boostability mismatch: "
                    f"{quest_id}"
                )

        bypassed_source_lines = {
            item["line_number"]
            for item in (
                [] if skills is None else skills["skills"]
            )
            if item["skill"] in bypassed_skills
        }

        if (
            review.get("proposed_direct_skill_requirements")
            != expected_skills
        ):
            raise ValueError(
                f"Proposed skills mismatch: {quest_id}"
            )

        if (
            review.get("proposed_direct_prerequisite_quest_ids")
            != expected_prerequisites
        ):
            raise ValueError(
                f"Proposed prerequisites mismatch: {quest_id}"
            )

        findings = review.get("review_findings")

        if not isinstance(findings, list):
            raise ValueError(
                f"Missing review findings: {quest_id}"
            )

        source_text = proposal["requirements_wikitext"]
        line_count = (
            len(source_text.splitlines())
            if isinstance(source_text, str)
            else 0
        )

        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError(
                    f"Invalid finding: {quest_id}"
                )

            if not (
                isinstance(finding.get("code"), str)
                and finding["code"].strip()
                and isinstance(finding.get("detail"), str)
                and finding["detail"].strip()
            ):
                raise ValueError(
                    f"Incomplete finding: {quest_id}"
                )

            line = finding.get("source_line")

            # A missing or empty frozen requirements field
            # has no numbered source lines. Allow a null
            # anchor only for those two source states.
            if line is None:
                if not (
                    proposal["requirements_status"]
                    in ("FIELD_ABSENT", "FIELD_EMPTY")
                    and line_count == 0
                ):
                    raise ValueError(
                        f"Invalid finding source line: {quest_id}"
                    )
            elif (
                type(line) is not int
                or not (1 <= line <= line_count)
            ):
                raise ValueError(
                    f"Invalid finding source line: {quest_id}"
                )

            if finding.get("status") not in (
                "UNRESOLVED",
                "RESOLVED",
            ):
                raise ValueError(
                    f"Invalid finding status: {quest_id}"
                )

            if finding["status"] == "RESOLVED":
                resolution = finding.get("resolution")

                if (
                    not isinstance(resolution, str)
                    or not resolution.strip()
                ):
                    raise ValueError(
                        f"Resolved finding has no explanation: {quest_id}"
                    )

                resolution_refs = finding.get(
                    "resolution_evidence_refs"
                )

                if (
                    not isinstance(resolution_refs, list)
                    or not resolution_refs
                    or not all(
                        isinstance(ref, str)
                        and ref.strip()
                        for ref in resolution_refs
                    )
                ):
                    raise ValueError(
                        f"Resolved finding has no evidence: {quest_id}"
                    )

        evidence = review.get("reviewer_evidence_refs")

        if (
            not isinstance(evidence, list)
            or not all(
                isinstance(ref, str) and ref.strip()
                for ref in evidence
            )
        ):
            raise ValueError(
                f"Invalid reviewer evidence: {quest_id}"
            )

        if not isinstance(
            review.get("review_notes"), str
        ):
            raise ValueError(
                f"Invalid review notes: {quest_id}"
            )

        unresolved = sum(
            finding["status"] == "UNRESOLVED"
            for finding in findings
        )

        if review_status == "APPROVED":
            quest_point_items = (
                [] if skills is None else skills["quest_points"]
            )
            if not verified_quest_point_assumption(
                review, quest_point_items
            ):
                raise ValueError(
                    f"Quest Point assumption requires verified policy: {quest_id}"
                )

            if unresolved:
                raise ValueError(
                    f"Approved review has unresolved findings: {quest_id}"
                )

            if proposal["requirements_status"] != "FIELD_PRESENT":
                # Missing/empty frozen fields can be approved
                # only through an explicit, independently
                # evidenced no-direct-requirements exception.
                # This does not treat missing data as proof.
                exception = review.get("missing_field_verification")

                source_findings = [
                    finding
                    for finding in findings
                    if (
                        finding.get("code")
                        == "INDEPENDENT_SOURCE_VERIFICATION"
                        and finding.get("status") == "RESOLVED"
                        and finding.get("source_line") is None
                        and isinstance(
                            finding.get("resolution"), str
                        )
                        and finding["resolution"].strip()
                        and isinstance(
                            finding.get("resolution_evidence_refs"),
                            list,
                        )
                    )
                ]

                source_refs = (
                    source_findings[0]["resolution_evidence_refs"]
                    if len(source_findings) == 1
                    else []
                )

                exception_refs = (
                    exception.get("independent_evidence_refs")
                    if isinstance(exception, dict)
                    else None
                )

                valid_evidence = (
                    isinstance(exception_refs, list)
                    and bool(exception_refs)
                    and all(
                        isinstance(ref, str) and ref.strip()
                        for ref in exception_refs
                    )
                    and exception_refs == source_refs
                    and all(ref in evidence for ref in exception_refs)
                    and any(
                        ref.startswith(
                            "https://oldschool.runescape.wiki/w/"
                        )
                        and not ref.endswith(
                            "Quests/Requirements_by_quest"
                        )
                        for ref in exception_refs
                    )
                )

                valid_exception = (
                    proposal["requirements_status"]
                    in ("FIELD_ABSENT", "FIELD_EMPTY")
                    and proposal["requirements_wikitext"] is None
                    and line_count == 0
                    and review[
                        "proposed_direct_skill_requirements"
                    ] == {}
                    and review[
                        "proposed_direct_prerequisite_quest_ids"
                    ] == []
                    and isinstance(exception, dict)
                    and exception.get("requirements_status")
                    == proposal["requirements_status"]
                    and exception.get("wiki_revision")
                    == proposal["wiki_revision"]
                    and exception.get("verification_method")
                    == "INDEPENDENT_PUBLISHED_OSRS_WIKI"
                    and exception.get("verification_decision")
                    == "NO_DIRECT_REQUIREMENTS_CONFIRMED"
                    and exception.get(
                        "verified_direct_skill_requirements"
                    ) == {}
                    and exception.get(
                        "verified_direct_prerequisite_quest_ids"
                    ) == []
                    and exception.get(
                        "verified_no_quest_point_requirement"
                    ) is True
                    and exception.get(
                        "non_skill_conditions_reviewed"
                    ) is True
                    and len(source_findings) == 1
                    and valid_evidence
                )

                if not valid_exception:
                    raise ValueError(
                        f"Approval of missing requirements field "
                        f"requires independently verified "
                        f"exception evidence: {quest_id}"
                    )

            if not evidence:
                raise ValueError(
                    f"Approved review has no reviewer evidence: {quest_id}"
                )

            approval = review.get("approval")

            if not isinstance(approval, dict):
                raise ValueError(
                    f"Missing approval record: {quest_id}"
                )

            if approval.get("scope") != "REQUIREMENTS_REVIEW_ONLY":
                raise ValueError(
                    f"Invalid approval scope: {quest_id}"
                )

            if (
                type(approval.get("wiki_revision")) is not int
                or approval["wiki_revision"]
                != proposal["wiki_revision"]
            ):
                raise ValueError(
                    f"Approval revision mismatch: {quest_id}"
                )

            for key in ("approved_by", "decision_notes"):
                value = approval.get(key)

                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Missing approval {key}: {quest_id}"
                    )

            timestamp = approval.get("approved_at_utc")

            if not isinstance(timestamp, str):
                raise ValueError(
                    f"Missing approval timestamp: {quest_id}"
                )

            try:
                approved_at = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
            except ValueError as error:
                raise ValueError(
                    f"Invalid approval timestamp: {quest_id}"
                ) from error

            if approved_at.utcoffset() != timedelta(0):
                raise ValueError(
                    f"Approval timestamp must be UTC: {quest_id}"
                )

        elif review.get("approval") is not None:
            raise ValueError(
                f"Pending review must not contain approval: {quest_id}"
            )

        if activation_status == "ACTIVATED":
            if review_status != "APPROVED":
                raise ValueError(
                    f"Unapproved activation: {quest_id}"
                )

            current = curated_lookup.get(quest_id)

            if current is None:
                raise ValueError(
                    f"Activated quest missing from curated data: {quest_id}"
                )

            # An exceptional numerical route may be omitted
            # only when the resulting curated quest retains
            # its exact verified, unmeasured alternative.
            #
            # Historical quests must not acquire undocumented
            # conditions, and a planning assumption must never
            # be represented as verified player evidence.
            if exceptional_requirement is None:
                expected_non_skill_conditions = ()

                # Elemental Workshop I has a source-verified
                # assisted-Mining alternative. Unlike the
                # historical Temple of Ikov bypass, this route
                # must remain explicitly unmeasured.
                #
                # The verified bypass helper has already
                # checked the frozen source, review findings
                # and evidence before reaching this point.
                if (
                    quest_id == "elemental_workshop_i"
                    and bypassed_skills == ("mining",)
                ):
                    bypass = review[
                        "verified_bypass_exceptions"
                    ][0]

                    if (
                        len(review["verified_bypass_exceptions"])
                        != 1
                        or bypass["skill"] != "mining"
                        or bypass["source_level"] != 20
                        or bypass["source_boostability"] != "yes"
                        or bypass["alternative_skill_requirements"]
                        != {}
                    ):
                        raise ValueError(
                            "Invalid assisted-Mining bypass: "
                            f"{quest_id}"
                        )

                    detail = (
                        "20 Mining (boostable), or the verified "
                        "alternative: "
                        + bypass["alternative_route"]
                        + " Unmeasured conditions: "
                        + "; ".join(
                            bypass["non_skill_conditions"]
                        )
                        + "."
                    )

                    expected_non_skill_conditions = (
                        QuestUnmeasuredCondition(
                            quest_id=quest_id,
                            condition_id=(
                                "assisted_elemental_rock_mining"
                            ),
                            condition_kind=(
                                "ALTERNATIVE_SKILL_OR_NON_SKILL"
                            ),
                            detail=detail,
                            source_wikitext_sha256=bypass[
                                "source_wikitext_sha256"
                            ],
                            evidence_status=(
                                "NOT_INDEPENDENTLY_MEASURED"
                            ),
                            planning_policy=(
                                "ASSUMED_FOR_PLANNING_ONLY"
                            ),
                            alternative_skill_route=(
                                bypass["skill"],
                                bypass["source_level"],
                                bypass["source_boostability"],
                            ),
                        ),
                    )
            else:
                condition = exceptional_requirement[
                    "non_skill_condition"
                ]
                alternative = exceptional_requirement[
                    "alternative_skill_route"
                ]

                if alternative is None:
                    alternative_tuple = None
                else:
                    alternative_tuple = (
                        alternative["skill"],
                        alternative["level"],
                        alternative["boostability"],
                    )

                expected_non_skill_conditions = (
                    QuestUnmeasuredCondition(
                        quest_id=quest_id,
                        condition_id=condition["condition_id"],
                        condition_kind=condition["kind"],
                        detail=condition["detail"],
                        source_wikitext_sha256=(
                            exceptional_requirement[
                                "source_wikitext_sha256"
                            ]
                        ),
                        evidence_status=(
                            condition["evidence_status"]
                        ),
                        planning_policy=(
                            condition["planning_policy"]
                        ),
                        partial_quest_id=(
                            condition["partial_quest_id"]
                        ),
                        alternative_skill_route=(
                            alternative_tuple
                        ),
                    ),
                )

            if (
                tuple(current.non_skill_conditions)
                != expected_non_skill_conditions
            ):
                raise ValueError(
                    f"Activated non-skill conditions mismatch: "
                    f"{quest_id}"
                )

            if (
                current.display_name != proposal["wiki_page_title"]
                or dict(current.direct_skill_requirements)
                != effective_skills
                or tuple(current.prerequisite_quest_ids)
                != tuple(expected_prerequisites)
                or current.access_flags
            ):
                raise ValueError(
                    f"Activated requirements mismatch: {quest_id}"
                )

            # An absent/empty frozen requirements field
            # is never, by itself, evidence of no requirements.
            # The APPROVED branch has already validated the
            # independent verification and its evidence.
            exception = review.get("missing_field_verification")

            verified_empty_source = (
                proposal["requirements_status"]
                in ("FIELD_ABSENT", "FIELD_EMPTY")
                and proposal["requirements_wikitext"] is None
                and skills is None
                and prerequisites is None
                and observations["progression"] is None
                and expected_skills == {}
                and expected_prerequisites == []
                and isinstance(exception, dict)
                and exception.get("requirements_status")
                == proposal["requirements_status"]
                and exception.get("wiki_revision")
                == proposal["wiki_revision"]
                and exception.get("verification_method")
                == "INDEPENDENT_PUBLISHED_OSRS_WIKI"
                and exception.get("verification_decision")
                == "NO_DIRECT_REQUIREMENTS_CONFIRMED"
                and exception.get(
                    "verified_direct_skill_requirements"
                ) == {}
                and exception.get(
                    "verified_direct_prerequisite_quest_ids"
                ) == []
                and exception.get(
                    "verified_no_quest_point_requirement"
                ) is True
                and exception.get(
                    "non_skill_conditions_reviewed"
                ) is True
                and isinstance(
                    exception.get("independent_evidence_refs"),
                    list,
                )
                and bool(
                    exception["independent_evidence_refs"]
                )
                and exception["independent_evidence_refs"]
                == review.get("reviewer_evidence_refs")
                and isinstance(review.get("approval"), dict)
            )

            verified_template_items = (
                verified_non_numeric_quest_templates(
                    proposal, review, curated_ids
                )
            )

            # Only the exact independently verified
            # exceptional source observation may bypass
            # its corresponding activation review block.
            exceptional_skill_lines = set()
            exceptional_skill_items = set()
            exceptional_progression_items = set()

            if exceptional_requirement is not None:
                verified_record = review[
                    "verified_exceptional_requirement"
                ]
                source_line = verified_record["source_line"]
                source_text = verified_record["source_text"]
                condition = exceptional_requirement[
                    "non_skill_condition"
                ]
                alternative = exceptional_requirement[
                    "alternative_skill_route"
                ]

                if (
                    condition["kind"]
                    == "ALTERNATIVE_SKILL_OR_NON_SKILL"
                ):
                    if alternative is None:
                        raise ValueError(
                            f"Missing alternative skill route: "
                            f"{quest_id}"
                        )

                    exceptional_skill_lines.add(
                        (source_line, source_text)
                    )
                    exceptional_skill_items.add(
                        (
                            alternative["skill"],
                            source_line,
                            source_text,
                        )
                    )

                elif (
                    condition["kind"]
                    == "PARTIAL_QUEST_PROGRESSION"
                ):
                    partial_quest_id = condition[
                        "partial_quest_id"
                    ]

                    if (
                        alternative is not None
                        or not partial_quest_id
                    ):
                        raise ValueError(
                            f"Invalid partial progression route: "
                            f"{quest_id}"
                        )

                    exceptional_progression_items.add(
                        (
                            source_line,
                            source_text,
                            (partial_quest_id,),
                            "PARTIAL",
                            "DIRECT",
                        )
                    )

                else:
                    raise ValueError(
                        f"Unsupported exceptional condition: "
                        f"{quest_id}"
                    )

            verified_conditional_items = (
                verified_conditional_skill_annotations(
                    proposal, review
                )
            )
            verified_conditional_lines = {
                (line, text)
                for _, line, text in verified_conditional_items
            }

            if any(
                skill in bypassed_skills
                for skill, _, _ in verified_conditional_items
            ):
                raise ValueError(
                    f"Conflicting conditional/bypass "
                    f"exception: {quest_id}"
                )

            # The curated model now supports explicit
            # boostability. Conditional or uncertain source
            # requirements still cannot be activated.
            if (
                not verified_empty_source
                and (
                    skills is None
                    or any(
                        (
                            item.get("type"),
                            item.get("line_number"),
                            item.get("source_text"),
                        ) not in verified_template_items
                        for item in skills["review_items"]
                    )
                    or any(
                        item["line_number"]
                        not in bypassed_source_lines
                        and (
                            item["line_number"],
                            item["source_text"],
                        ) not in verified_conditional_lines
                        and (
                            item["line_number"],
                            item["source_text"],
                        ) not in exceptional_skill_lines
                        for item in skills["conditional_skill_lines"]
                    )
                    or skills["combat_levels"]
                    or (
                        skills["quest_points"]
                        and not verified_quest_point_assumption(
                            review, skills["quest_points"]
                        )
                    )
                    or any(
                        item["boostable"] not in ("yes", "no")
                        or (
                            item["needs_condition_review"]
                            and item["skill"] not in bypassed_skills
                            and (
                                item["skill"],
                                item["line_number"],
                                item["source_text"],
                            ) not in verified_conditional_items
                            and (
                                item["skill"],
                                item["line_number"],
                                item["source_text"],
                            ) not in exceptional_skill_items
                        )
                        for item in skills["skills"]
                    )
                )
            ):
                raise ValueError(
                    f"Requirements need further modelling: {quest_id}"
                )

            # Activated boostability must match the effective
            # requirements after verified bypass omissions.
            # The original frozen source remains unchanged.

            expected_boostability = effective_boostability

            if (
                len(expected_boostability) != len(effective_skills)
                or set(expected_boostability) != set(effective_skills)
                or dict(current.direct_skill_boostability)
                != expected_boostability
            ):
                raise ValueError(
                    f"Activated boostability mismatch: {quest_id}"
                )

            if (
                not verified_empty_source
                and (
                    prerequisites is None
                    or prerequisites["direct_review"]
                    or prerequisites["mixed_completion_review"]
                    or prerequisites["other_nested_review"]
                    or prerequisites["inherited_prerequisite_observations"]
                    or prerequisites["top_level_completion_review"]
                    or prerequisites["structural_notes"]
                )
            ):
                raise ValueError(
                    f"Complex prerequisites need review: {quest_id}"
                )

            progression = observations["progression"]

            if (
                not verified_empty_source
                and (
                    progression is None
                    or progression["review_items"]
                    or any(
                        (
                            item["line_number"],
                            item["source_text"],
                            tuple(item["target_quest_ids"]),
                            item["progression_kind"],
                            item["context_kind"],
                        ) not in exceptional_progression_items
                        for item in progression[
                            "progression_observations"
                        ]
                    )
                    or progression["context_notes"]
                    or progression["non_quest_context_notes"]
                )
            ):
                raise ValueError(
                    f"Progression requirements need review: {quest_id}"
                )

            activation = review.get("activation")

            if not isinstance(activation, dict):
                raise ValueError(
                    f"Missing activation record: {quest_id}"
                )

            if (
                activation.get("scope")
                != "CURATED_QUEST_RESOLVER_ONLY"
                or type(activation.get("wiki_revision")) is not int
                or activation["wiki_revision"]
                != proposal["wiki_revision"]
            ):
                raise ValueError(
                    f"Invalid activation scope/revision: {quest_id}"
                )

            for key in ("activated_by", "decision_notes"):
                value = activation.get(key)

                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Missing activation {key}: {quest_id}"
                    )

            timestamp = activation.get("activated_at_utc")

            if not isinstance(timestamp, str):
                raise ValueError(
                    f"Missing activation timestamp: {quest_id}"
                )

            try:
                activated_at = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
            except ValueError as error:
                raise ValueError(
                    f"Invalid activation timestamp: {quest_id}"
                ) from error

            if activated_at.utcoffset() != timedelta(0):
                raise ValueError(
                    f"Activation timestamp must be UTC: {quest_id}"
                )

        elif review.get("activation") is not None:
            raise ValueError(
                f"Inactive review contains activation: {quest_id}"
            )

        results.append((quest_id, unresolved))

    return results


if __name__ == "__main__":
    results = validate_reviews()

    print("=== QUEST REQUIREMENTS REVIEW VALIDATION ===")
    print("Reviews validated:", len(results))

    for quest_id, unresolved in results:
        print(
            f"{quest_id}: VALID, "
            f"{unresolved} unresolved findings"
        )

    print()
    print("VALIDATION PASSED")

    saved_reviews = read_json(REVIEWS_PATH)["reviews"]

    approved = sum(
        review["review_status"] == "APPROVED"
        for review in saved_reviews
    )
    pending = sum(
        review["review_status"] == "PENDING"
        for review in saved_reviews
    )

    print("Approved reviews:", approved)
    print("Pending reviews:", pending)
    activated = sum(
        review["activation_status"] == "ACTIVATED"
        for review in saved_reviews
    )

    print("Imported requirements activated:", activated)
    print("No files or databases modified.")
