"""Reconcile audited nested Wiki references with existing observations.

This module does not create quest dependencies or evaluate
player eligibility. Unknown or changed references stay in review.
"""

KNOWN_NESTED_REFERENCES = {
    ("ratcatchers", 6): {
        "source_text": "**[[The Giant Dwarf]] started",
        "kind": "QUEST_PROGRESSION",
        "target": "the_giant_dwarf",
        "context": "DIRECT_ACCESS",
    },
    ("recipe_for_disaster_freeing_sir_amik_varze", 3): {
        "source_text": "**Started [[Legends' Quest]]",
        "kind": "QUEST_PROGRESSION",
        "target": "legends_quest",
        "context": "DIRECT_ACCESS",
    },
    ("miniquest_the_generals_shadow", 2): {
        "source_text": (
            "**Started [[Desert Treasure I]], "
            "for the [[ring of visibility]]"
        ),
        "kind": "QUEST_PROGRESSION",
        "target": "desert_treasure_i",
        "context": "TRANSITIVE",
    },
    ("my_arms_big_adventure", 11): {
        "source_text": (
            "**Acquiring 100% Tai Bwo Favour rating is a "
            "requirement for the [[Medium Karamja Diary]]. "
            "If completion of the medium diary is desired, "
            "it is recommended to get 100% prior to "
            "starting this quest"
        ),
        "kind": "OPTIONAL_RECOMMENDATION",
    },
    ("miniquest_curse_of_the_empty_lord", 2): {
        "source_text": (
            "**{{SCP|Thieving|53|link=yes}} "
            "{{Boostable|no}} {{Questreqstart|yes}} "
            "to obtain the [[Ring of visibility]]"
        ),
        "kind": "NESTED_SKILL_CONDITION",
        "skill": "thieving",
        "level": 53,
        "required_to_start": "yes",
    },
}


def reconcile_nested_reviews(
    quest_id, prerequisites, progression, skills
):
    """Cross-reference nested review lines without promoting them.

    Only five exact audited sources can be reconciled.
    A changed line or missing matching observation stays open.
    """
    result = {
        "quest_id": quest_id,
        "linked_observations": [],
        "unresolved_nested_reviews": [],
    }

    nested = prerequisites["other_nested_review"]

    for item in nested:
        line_number = item["line_number"]
        source_text = item["source_text"]

        specification = KNOWN_NESTED_REFERENCES.get(
            (quest_id, line_number)
        )

        if specification is None:
            result["unresolved_nested_reviews"].append({
                **item,
                "reason": "UNCLASSIFIED_NESTED_REFERENCE",
            })
            continue

        if source_text != specification["source_text"]:
            result["unresolved_nested_reviews"].append({
                **item,
                "reason": "AUDITED_SOURCE_CHANGED",
            })
            continue

        kind = specification["kind"]

        if kind == "QUEST_PROGRESSION":
            candidates = [
                observation
                for observation in progression[
                    "progression_observations"
                ]
                if (
                    observation["line_number"] == line_number
                    and observation["source_text"] == source_text
                    and specification["target"]
                    in observation["target_quest_ids"]
                    and observation["context_kind"]
                    == specification["context"]
                )
            ]

        elif kind == "OPTIONAL_RECOMMENDATION":
            candidates = [
                observation
                for observation in progression[
                    "non_quest_context_notes"
                ]
                if (
                    observation["line_number"] == line_number
                    and observation["source_text"] == source_text
                    and observation["note_kind"]
                    == "OPTIONAL_RECOMMENDATION"
                )
            ]

        elif kind == "NESTED_SKILL_CONDITION":
            candidates = [
                observation
                for observation in skills["skills"]
                if (
                    observation["line_number"] == line_number
                    and observation["source_text"] == source_text
                    and observation["skill"]
                    == specification["skill"]
                    and observation["level"]
                    == specification["level"]
                    and observation["required_to_start"]
                    == specification["required_to_start"]
                )
            ]

        else:
            raise ValueError(
                f"Unexpected reconciliation kind: {kind}"
            )

        candidates = [
            candidate
            for candidate in candidates
            if candidate.get("verification_status")
            == "UNVERIFIED"
        ]

        if len(candidates) != 1:
            result["unresolved_nested_reviews"].append({
                **item,
                "reason": "MATCHING_OBSERVATION_UNAVAILABLE",
            })
            continue

        result["linked_observations"].append({
            "line_number": line_number,
            "source_text": source_text,
            "observation_kind": kind,
            "observation": candidates[0],
            "verification_status": "UNVERIFIED",
            "eligibility_status": "NOT_EVALUATED",
        })

    return result
