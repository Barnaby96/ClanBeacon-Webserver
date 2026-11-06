"""Display one OSRS requirements proposal for manual review.

This is a read-only review tool. It does not approve
requirements or change player accessibility.
"""

import argparse
import json
from pathlib import Path

from utils.osrs_quest_data import (
    get_curated_quest_requirements,
)


PROPOSALS_PATH = Path(
    "data/osrs_requirement_proposals_v1.json"
)


def load_proposals():
    payload = json.loads(
        PROPOSALS_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    if (
        payload.get("schema_version") != 1
        or payload.get("purpose") != "REVIEW_ONLY"
    ):
        raise ValueError(
            "Unexpected requirements proposal schema."
        )

    proposals = payload["proposals"]

    if len(proposals) != 214:
        raise ValueError(
            "Expected 214 requirements proposals."
        )

    by_id = {}

    for proposal in proposals:
        quest_id = proposal["quest_id"]

        if quest_id in by_id:
            raise ValueError(
                f"Duplicate proposal: {quest_id}"
            )

        by_id[quest_id] = proposal

    return by_id


def print_observations(heading, observations):
    print()
    print("=" * 70)
    print(heading)

    if observations is None:
        print(
            "No observations extracted from this "
            "requirements field."
        )
        return

    for category, values in observations.items():
        print()
        print("---", category, "---")

        if isinstance(values, list):
            print("Items:", len(values))

            for number, item in enumerate(values, 1):
                print()
                print(f"Item {number}:")
                print(
                    json.dumps(
                        item,
                        indent=2,
                        ensure_ascii=False,
                    )
                )

        elif isinstance(values, dict):
            print(
                json.dumps(
                    values,
                    indent=2,
                    ensure_ascii=False,
                )
            )

        elif values is None:
            print("None")

        else:
            print(repr(values))


def review_quest(quest_id):
    proposals = load_proposals()

    if quest_id not in proposals:
        raise ValueError(
            f"Unknown quest ID: {quest_id}"
        )

    proposal = proposals[quest_id]

    if (
        proposal["approval_status"] != "UNVERIFIED"
        or proposal["eligibility_status"] != "NOT_EVALUATED"
    ):
        raise ValueError(
            "Unexpected proposal approval state. "
            "Review tool cannot approve requirements."
        )

    curated_lookup = {
        quest.quest_id: quest
        for quest in get_curated_quest_requirements()
    }

    print("=== OSRS QUEST REQUIREMENTS REVIEW ===")
    print()
    print("Quest ID:", quest_id)
    print("Title:", proposal["wiki_page_title"])
    print("Type:", proposal["record_type"])
    print("Wiki revision:", proposal["wiki_revision"])
    print(
        "Revision timestamp:",
        proposal["wiki_revision_timestamp"],
    )
    print(
        "Source status:",
        proposal["requirements_status"],
    )
    print(
        "Approval status:",
        proposal["approval_status"],
    )
    print(
        "Eligibility status:",
        proposal["eligibility_status"],
    )

    print()
    print("=" * 70)
    print("ORIGINAL WIKI REQUIREMENTS")

    wikitext = proposal["requirements_wikitext"]

    if wikitext is None:
        print(
            "No requirements field text recorded. "
            "This does not prove there are no requirements."
        )
    else:
        for number, line in enumerate(
            wikitext.splitlines(), 1
        ):
            print(f"{number:3}: {line}")

    print_observations(
        "PARSED SKILL OBSERVATIONS",
        proposal["observations"]["skills"],
    )

    print_observations(
        "PARSED PREREQUISITE OBSERVATIONS",
        proposal["observations"]["prerequisites"],
    )

    print_observations(
        "PARSED PROGRESSION OBSERVATIONS",
        proposal["observations"]["progression"],
    )

    print()
    print("=" * 70)
    print("EXISTING CURATED REQUIREMENTS")

    curated = curated_lookup.get(quest_id)

    if curated is None:
        print(
            "Not currently curated. "
            "No approved requirements are inferred."
        )
    else:
        print("Quest ID:", curated.quest_id)
        print("Display name:", curated.display_name)
        print(
            "Direct skill requirements:",
            dict(curated.direct_skill_requirements),
        )
        print(
            "Prerequisite quest IDs:",
            tuple(curated.prerequisite_quest_ids),
        )
        print(
            "Access flags:",
            sorted(str(flag.value) for flag in curated.access_flags),
        )

    print()
    print("=" * 70)
    print("REVIEW STATUS")
    print("No approval decision made.")
    print("No eligibility assessment performed.")
    print("No files or databases modified.")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Inspect an unverified quest requirements proposal."
        )
    )
    parser.add_argument(
        "--quest",
        required=True,
        help="Canonical quest ID, e.g. regicide",
    )

    args = parser.parse_args()
    review_quest(args.quest)


if __name__ == "__main__":
    main()
