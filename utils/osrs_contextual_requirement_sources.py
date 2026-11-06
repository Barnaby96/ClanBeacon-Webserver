"""Curated contextual notes from frozen OSRS Wiki sources.

These are observations, not independently enforceable
eligibility requirements. Source changes require review.
"""

SOURCE_SPECS = {
    "tai_bwo_wannai_trio": {
        "wiki_revision": 15376159,
        "line_number": 3,
        "source_text": (
            "* {{SCP|Fishing|5|link=yes}} "
            "{{Boostable|Yes}} {{Questreqstart|no}} "
            "<ref>Level 65 is required if you wish to catch "
            "the [[Raw karambwan]] yourself.</ref>"
            "<!--Do not add 30 Firemaking-->"
        ),
        "note_kind": "OPTIONAL_METHOD_LEVEL",
        "listed_skill": "fishing",
        "listed_level": 5,
        "advisory_level": 65,
        "required_to_start": "NO",
        "scope": "QUEST",
        "note": (
            "Fishing 65 applies to catching raw karambwan "
            "personally, not to the quest's listed Fishing "
            "5 requirement."
        ),
    },
    "troll_stronghold": {
        "wiki_revision": 15326717,
        "line_number": 2,
        "source_text": (
            "* {{SCP|Agility|15|link=yes}} "
            "{{Boostable|yes}} {{Questreqstart|no}} "
            "(47 is recommended)"
        ),
        "note_kind": "RECOMMENDED_LEVEL",
        "listed_skill": "agility",
        "listed_level": 15,
        "advisory_level": 47,
        "required_to_start": "NO",
        "scope": "QUEST",
        "note": (
            "Agility 47 is recommended, not the listed "
            "minimum of Agility 15."
        ),
    },
    "the_fremennik_isles": {
        "wiki_revision": 15380442,
        "line_number": 2,
        "source_text": (
            "*{{SCP|Construction|20|link=yes}} "
            "{{Boostable|yes}}  {{Questreqstart|no}} "
            "<ref>Only required to fix the bridges "
            "later in the quest.</ref>"
        ),
        "note_kind": "LATER_STAGE_REQUIREMENT",
        "listed_skill": "construction",
        "listed_level": 20,
        "advisory_level": None,
        "required_to_start": "NO",
        "scope": "QUEST",
        "note": (
            "Construction 20 is required to fix bridges "
            "later in the quest; not required to start."
        ),
    },
    "grim_tales": {
        "wiki_revision": 15363205,
        "line_number": 6,
        "source_text": (
            "*{{SCP|Agility|59|link=yes}} "
            "{{Boostable|yes}}  {{Questreqstart|no}} "
            "<ref>If boosting, note that there are "
            "two skill checks.</ref>"
        ),
        "note_kind": "REPEATED_SKILL_CHECK",
        "listed_skill": "agility",
        "listed_level": 59,
        "advisory_level": None,
        "required_to_start": "NO",
        "scope": "QUEST",
        "note": (
            "Two Agility checks occur when boosting; "
            "the source does not specify an additional "
            "numeric level requirement."
        ),
    },
    "recipe_for_disaster": {
        "wiki_revision": 15382871,
        "line_number": 20,
        "source_text": (
            "*The ability to defeat high levelled monsters, "
            "several of which have to be defeated without "
            "using {{SCP|Prayer|link=yes}}"
        ),
        "note_kind": "COMBAT_RESTRICTION",
        "listed_skill": None,
        "listed_level": None,
        "advisory_level": None,
        "required_to_start": "UNKNOWN",
        "scope": "PARENT_AGGREGATE",
        "note": (
            "The Recipe for Disaster parent summary describes "
            "combat restrictions involving Prayer. This is "
            "not a numeric Prayer-level requirement and must "
            "not automatically apply to each subquest."
        ),
    },
}


def normalise_source_whitespace(value):
    return " ".join(value.strip().split())


def extract_curated_contextual_observations(record):
    """Preserve exactly audited contextual source observations."""
    if not isinstance(record, dict):
        raise TypeError("Source record must be a dictionary.")

    quest_id = record.get("quest_id")

    if quest_id not in SOURCE_SPECS:
        return []

    specification = SOURCE_SPECS[quest_id]

    if (
        record.get("record_type") != "QUEST"
        or record.get("requirements_status") != "FIELD_PRESENT"
    ):
        raise ValueError(
            f"Unexpected source status for {quest_id}"
        )

    if record.get("wiki_revision") != specification["wiki_revision"]:
        raise ValueError(
            f"Wiki revision changed for {quest_id}"
        )

    raw = record.get("requirements_wikitext")

    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            f"Missing requirements for {quest_id}"
        )

    expected = normalise_source_whitespace(
        specification["source_text"]
    )

    matches = [
        (number, line)
        for number, line in enumerate(raw.splitlines(), 1)
        if normalise_source_whitespace(line) == expected
    ]

    if (
        len(matches) != 1
        or matches[0][0] != specification["line_number"]
    ):
        raise ValueError(
            f"Contextual source requires review: {quest_id}"
        )

    line_number, source_text = matches[0]

    return [{
        "source_quest_id": quest_id,
        "wiki_revision": record["wiki_revision"],
        "line_number": line_number,
        "source_text": source_text,
        "note_kind": specification["note_kind"],
        "listed_skill": specification["listed_skill"],
        "listed_level": specification["listed_level"],
        "advisory_level": specification["advisory_level"],
        "required_to_start": specification["required_to_start"],
        "scope": specification["scope"],
        "note": specification["note"],
        "verification_status": "UNVERIFIED",
        "eligibility_status": "NOT_EVALUATED",
    }]
