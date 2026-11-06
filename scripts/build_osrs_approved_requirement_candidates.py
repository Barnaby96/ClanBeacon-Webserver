"""Prepare approved OSRS requirements for integration review.

Only explicitly approved reviews are considered.
No curated requirements, player access rules or generator
settings are changed by this module.
"""

from scripts.validate_osrs_requirement_reviews import (
    PROPOSALS_PATH,
    REVIEWS_PATH,
    read_json,
    validate_reviews,
)
from utils.osrs_quest_data import (
    get_curated_quest_requirements,
)


def build_approved_requirement_candidates():
    # Validate the complete review dataset first.
    validate_reviews()

    proposal_data = read_json(PROPOSALS_PATH)
    review_data = read_json(REVIEWS_PATH)

    proposals = {
        proposal["quest_id"]: proposal
        for proposal in proposal_data["proposals"]
    }

    curated = {
        quest.quest_id: quest
        for quest in get_curated_quest_requirements()
    }

    candidates = []

    for review in review_data["reviews"]:
        if review["review_status"] != "APPROVED":
            continue

        activation_status = review["activation_status"]

        if activation_status not in (
            "NOT_ACTIVATED",
            "ACTIVATED",
        ):
            raise ValueError(
                "Unexpected approved review activation status."
            )

        quest_id = review["quest_id"]
        proposal = proposals[quest_id]

        skill_observations = proposal["observations"]["skills"]

        if skill_observations is None:
            # Validation above must already have approved
            # the independently evidenced exception.
            # Missing source data alone proves nothing.
            exception = review.get("missing_field_verification")

            valid_exception = (
                proposal["requirements_status"]
                in ("FIELD_ABSENT", "FIELD_EMPTY")
                and proposal["requirements_wikitext"] is None
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
                and exception.get("independent_evidence_refs")
                and exception["independent_evidence_refs"]
                == review.get("reviewer_evidence_refs")
                and review["proposed_direct_skill_requirements"]
                == {}
                and review[
                    "proposed_direct_prerequisite_quest_ids"
                ] == []
            )

            if not valid_exception:
                raise ValueError(
                    "Unverified missing skill observations: "
                    f"{quest_id}"
                )

            skills = []
        else:
            skills = skill_observations["skills"]

        proposed_skills = dict(
            review["proposed_direct_skill_requirements"]
        )

        proposed_prerequisites = tuple(
            review["proposed_direct_prerequisite_quest_ids"]
        )

        current = curated.get(quest_id)

        if current is None:
            comparison = "NEW_APPROVED_CANDIDATE"
        elif (
            dict(current.direct_skill_requirements)
            == proposed_skills
            and tuple(current.prerequisite_quest_ids)
            == proposed_prerequisites
        ):
            comparison = "MATCHES_EXISTING_CURATED"
        else:
            comparison = "DIFFERS_FROM_EXISTING_CURATED"

        # These details are not represented in the existing
        # QuestRequirement model and must not be discarded.
        unrepresented = [
            {
                "skill": item["skill"],
                "level": item["level"],
                "boostable": item["boostable"],
            }
            for item in skills
            if item["boostable"] != "no"
        ]

        candidates.append({
            "quest_id": quest_id,
            "title": proposal["wiki_page_title"],
            "wiki_revision": review["wiki_revision"],
            "review_status": "APPROVED",
            "activation_status": activation_status,
            "comparison": comparison,
            "direct_skill_requirements": proposed_skills,
            "direct_prerequisite_quest_ids": (
                proposed_prerequisites
            ),
            "skill_observations": tuple(
                dict(item) for item in skills
            ),
            "boostability_not_in_curated_model": tuple(
                unrepresented
            ),
            "integration_status": (
                "ACTIVATED_CURATED_ONLY"
                if activation_status == "ACTIVATED"
                else "PREVIEW_ONLY"
            ),
        })

    return tuple(candidates)


def main():
    candidates = build_approved_requirement_candidates()

    print("=== APPROVED REQUIREMENTS INTEGRATION PREVIEW ===")
    print("Approved candidates:", len(candidates))
    print()

    for candidate in candidates:
        print("=" * 65)
        print("Quest:", candidate["title"])
        print("ID:", candidate["quest_id"])
        print("Wiki revision:", candidate["wiki_revision"])
        print("Comparison:", candidate["comparison"])
        print(
            "Direct skills:",
            candidate["direct_skill_requirements"],
        )
        print(
            "Direct prerequisites:",
            candidate["direct_prerequisite_quest_ids"],
        )
        print(
            "Boostable/uncertain requirements:",
            candidate["boostability_not_in_curated_model"],
        )
        print(
            "Integration status:",
            candidate["integration_status"],
        )
        print()

    # Validate every approved candidate, without assuming
    # a fixed number of approved quests.
    quest_ids = [
        candidate["quest_id"]
        for candidate in candidates
    ]

    if len(quest_ids) != len(set(quest_ids)):
        raise ValueError(
            "Duplicate approved integration candidates."
        )

    for candidate in candidates:
        quest_id = candidate["quest_id"]
        activation = candidate["activation_status"]

        if candidate["review_status"] != "APPROVED":
            raise ValueError(
                f"Unapproved integration candidate: {quest_id}"
            )

        expected_status = {
            "NOT_ACTIVATED": "PREVIEW_ONLY",
            "ACTIVATED": "ACTIVATED_CURATED_ONLY",
        }.get(activation)

        if (
            expected_status is None
            or candidate["integration_status"]
            != expected_status
        ):
            raise ValueError(
                f"Inconsistent integration state: {quest_id}"
            )

        if (
            activation == "ACTIVATED"
            and candidate["comparison"]
            != "MATCHES_EXISTING_CURATED"
        ):
            raise ValueError(
                f"Activated requirements differ from curated: {quest_id}"
            )

    print("=== INTEGRATION STATE VALIDATION PASSED ===")
    print("Approved records only.")
    print(
        "Activated in curated resolver:",
        sum(
            item["integration_status"]
            == "ACTIVATED_CURATED_ONLY"
            for item in candidates
        ),
    )
    print("No changes made by this preview.")
    print("No files or databases modified.")


if __name__ == "__main__":
    main()
