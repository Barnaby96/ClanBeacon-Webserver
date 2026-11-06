"""Build unverified OSRS quest-requirement proposals.

Source observations are not approved requirements.
This module must not be used to establish player eligibility.
"""

import json
from collections import Counter
from pathlib import Path

from utils.osrs_quest_skill_parser import (
    parse_skill_requirements,
)
from utils.osrs_quest_prerequisite_parser import (
    build_quest_title_lookup,
    extract_direct_prerequisite_candidates,
    extract_progression_observations,
)


DATA_DIR = Path("data")


def load_json(filename):
    return json.loads(
        (DATA_DIR / filename).read_text(
            encoding="utf-8-sig"
        )
    )


def build_requirement_proposals():
    quest_catalogue = load_json(
        "osrs_quest_catalogue_v1.json"
    )
    miniquest_catalogue = load_json(
        "osrs_miniquest_catalogue_v1.json"
    )

    quest_sources = load_json(
        "osrs_quest_requirements_source_v1.json"
    )["requirements_records"]

    miniquest_sources = load_json(
        "osrs_miniquest_requirements_source_v1.json"
    )["requirements_records"]

    catalogue_entries = (
        quest_catalogue["quest_entries"]
        + miniquest_catalogue["miniquest_entries"]
    )

    source_records = quest_sources + miniquest_sources

    if len(catalogue_entries) != 214:
        raise ValueError(
            "Expected 214 catalogue entries."
        )

    if len(source_records) != 214:
        raise ValueError(
            "Expected 214 source requirement records."
        )

    catalogue_ids = [
        entry["quest_id"]
        for entry in catalogue_entries
    ]

    source_ids = [
        record["quest_id"]
        for record in source_records
    ]

    if (
        len(set(catalogue_ids)) != 214
        or len(set(source_ids)) != 214
        or set(catalogue_ids) != set(source_ids)
    ):
        raise ValueError(
            "Catalogue and source IDs do not match uniquely."
        )

    title_lookup = build_quest_title_lookup({
        "quest_entries": catalogue_entries,
    })

    proposals = []

    for record in source_records:
        quest_id = record["quest_id"]
        status = record["requirements_status"]
        wikitext = record["requirements_wikitext"]

        if status == "FIELD_PRESENT":
            if (
                not isinstance(wikitext, str)
                or not wikitext.strip()
            ):
                raise ValueError(
                    f"Missing requirements text: {quest_id}"
                )

            try:
                skills = parse_skill_requirements(
                    quest_id,
                    wikitext,
                )

                prerequisites = (
                    extract_direct_prerequisite_candidates(
                        quest_id,
                        wikitext,
                        title_lookup,
                    )
                )

                progression = (
                    extract_progression_observations(
                        quest_id,
                        wikitext,
                        title_lookup,
                    )
                )
            except Exception as error:
                raise RuntimeError(
                    f"Could not parse requirements for "
                    f"{quest_id}"
                ) from error

        elif status in (
            "FIELD_ABSENT",
            "FIELD_EMPTY",
            "IGNORED_TUTORIAL",
        ):
            if wikitext is not None:
                raise ValueError(
                    f"Unexpected requirements text: {quest_id}"
                )

            # No field is not evidence of no requirements.
            skills = None
            prerequisites = None
            progression = None

        else:
            raise ValueError(
                f"Unknown source status: {quest_id}: {status}"
            )

        proposals.append({
            "quest_id": quest_id,
            "record_type": record["record_type"],
            "wiki_page_title": record["wiki_page_title"],
            "wiki_revision": record["wiki_revision"],
            "wiki_revision_timestamp": record[
                "wiki_revision_timestamp"
            ],
            "requirements_status": status,
            "requirements_wikitext": wikitext,
            "approval_status": "UNVERIFIED",
            "eligibility_status": "NOT_EVALUATED",
            "observations": {
                "skills": skills,
                "prerequisites": prerequisites,
                "progression": progression,
            },
        })

    # Confirm proposals can be safely serialised later.
    json.dumps(proposals, ensure_ascii=False)

    return tuple(proposals)


if __name__ == "__main__":
    proposals = build_requirement_proposals()

    statuses = Counter(
        proposal["requirements_status"]
        for proposal in proposals
    )

    print("=== REQUIREMENTS PROPOSAL PREVIEW ===")
    print("Proposals:", len(proposals))

    for status, count in sorted(statuses.items()):
        print(f"{status}: {count}")

    print()
    print("Approval statuses:", sorted({
        proposal["approval_status"]
        for proposal in proposals
    }))

    print("Eligibility statuses:", sorted({
        proposal["eligibility_status"]
        for proposal in proposals
    }))

    print()
    print("=== SAMPLE PROPOSALS ===")

    by_id = {
        proposal["quest_id"]: proposal
        for proposal in proposals
    }

    for quest_id in (
        "dragon_slayer_ii",
        "regicide",
        "recipe_for_disaster",
        "cooks_assistant",
    ):
        proposal = by_id[quest_id]
        observations = proposal["observations"]

        print()
        print("QUEST:", quest_id)
        print(
            "  Source status:",
            proposal["requirements_status"],
        )
        print(
            "  Approval:",
            proposal["approval_status"],
        )

        for category, value in observations.items():
            if value is None:
                print(
                    f"  {category}: "
                    "not extracted (source field absent/empty)"
                )
            elif isinstance(value, dict):
                print(
                    f"  {category}: "
                    f"dict with keys {list(value)}"
                )
            elif isinstance(value, (list, tuple)):
                print(
                    f"  {category}: "
                    f"{len(value)} observations"
                )
            else:
                print(
                    f"  {category}: "
                    f"{type(value).__name__}"
                )

    print()
    print("=== PREVIEW COMPLETE ===")
    print("No proposals approved.")
    print("No data files written.")
    print("No database or live generator changes.")
