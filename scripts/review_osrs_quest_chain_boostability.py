"""Inspect boostability across existing curated OSRS quest chains.

Curated quest relationships establish the chain.
Unverified Wiki proposals supply review-only observations.

This module does not assess player access, approve requirements
or modify the live quest resolver.
"""

import json
from pathlib import Path

from utils.osrs_quest_data import (
    resolve_curated_quest_skill_requirements,
)
from utils.osrs_skill_boostability import (
    classify_skill_requirement,
)


PROPOSALS_PATH = Path(
    "data/osrs_requirement_proposals_v1.json"
)


def build_chain_boostability_review(required_quest_ids):
    payload = json.loads(
        PROPOSALS_PATH.read_text(encoding="utf-8-sig")
    )

    if (
        payload.get("schema_version") != 1
        or payload.get("purpose") != "REVIEW_ONLY"
    ):
        raise ValueError("Unexpected proposal dataset.")

    proposals = payload["proposals"]

    if len(proposals) != 214:
        raise ValueError("Expected 214 proposals.")

    by_id = {}

    for proposal in proposals:
        quest_id = proposal["quest_id"]

        if quest_id in by_id:
            raise ValueError(
                f"Duplicate proposal: {quest_id}"
            )

        if (
            proposal["approval_status"] != "UNVERIFIED"
            or proposal["eligibility_status"] != "NOT_EVALUATED"
        ):
            raise ValueError(
                f"Unexpected proposal state: {quest_id}"
            )

        by_id[quest_id] = proposal

    resolved = resolve_curated_quest_skill_requirements(
        required_quest_ids
    )

    chain = []

    for quest_id in resolved.quest_ids:
        proposal = by_id.get(quest_id)

        if proposal is None:
            raise ValueError(
                f"No source proposal for {quest_id}"
            )

        source_status = proposal["requirements_status"]
        skill_result = proposal["observations"]["skills"]

        if source_status == "FIELD_PRESENT":
            if not isinstance(skill_result, dict):
                raise ValueError(
                    f"Missing parsed skills: {quest_id}"
                )

            observations = skill_result["skills"]

            if not isinstance(observations, list):
                raise ValueError(
                    f"Invalid skill observations: {quest_id}"
                )

        else:
            # Missing/empty Wiki fields are not evidence
            # that a quest has no requirements.
            if source_status not in (
                "FIELD_ABSENT",
                "FIELD_EMPTY",
                "IGNORED_TUTORIAL",
            ):
                raise ValueError(
                    f"Unexpected source status: {quest_id}"
                )

            if skill_result is not None:
                raise ValueError(
                    f"Unexpected parsed skills: {quest_id}"
                )

            observations = None

        skill_entries = None

        if observations is not None:
            # Keep every observation separately, even when
            # several quests require the same skill.
            skill_entries = tuple({
                "quest_id": quest_id,
                "skill": item["skill"],
                "level": item["level"],
                "boostable": item["boostable"],
                "required_to_start": item[
                    "required_to_start"
                ],
                "condition_kind": item[
                    "condition_kind"
                ],
                "line_number": item["line_number"],
                "verification_status": item[
                    "verification_status"
                ],
            } for item in observations)

        chain.append({
            "quest_id": quest_id,
            "requirements_status": source_status,
            "skill_observations": skill_entries,
        })

    return tuple(chain)



def group_chain_skill_observations(chain):
    """Group source observations by skill without flattening them.

    Retain originating quests, levels and boostability.
    Absent source fields remain explicitly unknown.
    No eligibility or approval decision is made.
    """
    grouped = {}
    missing_source_fields = []

    for quest in chain:
        quest_id = quest["quest_id"]
        observations = quest["skill_observations"]

        if observations is None:
            missing_source_fields.append(quest_id)
            continue

        for observation in observations:
            if observation["verification_status"] != "UNVERIFIED":
                raise ValueError(
                    f"Unexpected verification status: {quest_id}"
                )

            skill = observation["skill"]

            grouped.setdefault(skill, []).append(
                dict(observation)
            )

    return {
        "requirements_by_skill": {
            skill: tuple(items)
            for skill, items in sorted(grouped.items())
        },
        "quests_with_missing_source_fields": tuple(
            missing_source_fields
        ),
        "eligibility_status": "NOT_EVALUATED",
    }


def main():
    chain = build_chain_boostability_review(
        ("regicide",)
    )

    print("=== REGICIDE QUEST CHAIN BOOSTABILITY ===")
    print("Quest chain entries:", len(chain))

    observation_count = 0
    unknown_source_count = 0

    for quest in chain:
        print()
        print("QUEST:", quest["quest_id"])
        print(
            "  Source status:",
            quest["requirements_status"],
        )

        observations = quest["skill_observations"]

        if observations is None:
            unknown_source_count += 1
            print(
                "  Skills: NOT EXTRACTED "
                "(source requirements absent/empty)"
            )
            continue

        print(
            "  Skill observations:",
            len(observations),
        )

        for item in observations:
            observation_count += 1

            print(
                f"  - {item['skill']} {item['level']}: "
                f"boostable={item['boostable']}, "
                f"start={item['required_to_start']}, "
                f"line={item['line_number']}, "
                f"verification={item['verification_status']}"
            )

    print()
    print("=== REGICIDE EXAMPLE ===")

    regicide = next(
        quest for quest in chain
        if quest["quest_id"] == "regicide"
    )

    agility = next(
        item
        for item in regicide["skill_observations"]
        if item["skill"] == "agility"
    )

    example = classify_skill_requirement(
        agility["level"],
        agility["boostable"],
        55,
    )

    assert example == "BOOST_REQUIRED_UNCONFIRMED"

    print("Player Agility: 55")
    print("Regicide requirement: Agility 56, boostable")
    print("Skill assessment:", example)

    print()
    grouped = group_chain_skill_observations(chain)

    print("=== GROUPED SKILL REQUIREMENTS ===")

    for skill, observations in grouped[
        "requirements_by_skill"
    ].items():
        print()
        print("SKILL:", skill)

        for item in observations:
            print(
                f"  {item['quest_id']}: "
                f"level={item['level']}, "
                f"boostable={item['boostable']}, "
                f"line={item['line_number']}"
            )

    print()
    print(
        "Quests with missing source fields:",
        grouped["quests_with_missing_source_fields"],
    )
    print(
        "Eligibility:",
        grouped["eligibility_status"],
    )

    # These are observations, not approved requirements.
    assert set(grouped["requirements_by_skill"]) == {
        "agility", "crafting", "ranged"
    }
    assert grouped["quests_with_missing_source_fields"] == (
        "plague_city",
    )
    assert grouped["eligibility_status"] == "NOT_EVALUATED"

    print()
    print("=== REVIEW SUMMARY ===")
    print("Individual skill observations:", observation_count)
    print("Quests with absent/empty source:", unknown_source_count)
    print("Quest relationships: existing curated data")
    print("Skill observations: UNVERIFIED Wiki proposals")
    print("No overall accessibility decision made.")
    print("No requirements approved or activated.")
    print("No files or databases modified.")


if __name__ == "__main__":
    main()
