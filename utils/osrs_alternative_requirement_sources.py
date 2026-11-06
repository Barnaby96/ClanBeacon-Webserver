'''Curated alternative requirements from saved OSRS Wiki sources.

The exact source wording must match an audited pattern.
These observations do not establish player eligibility.
'''

from utils.osrs_requirement_expressions import (
    RequirementNode,
    RequirementObservation,
)


def node(kind, **kwargs):
    return RequirementNode(kind=kind, **kwargs)


# Each entry is tied to a complete, audited Wiki requirement line.
# Changes to substantive wording require a fresh review.
CURATED_ALTERNATIVES = {
    "tears_of_guthix": {
        "source_text": '* {{SCP|Crafting|20|link=yes}} {{Boostable|yes}} {{Questreqstart|no}} <ref>Adding the sapphire lens to a [[Bullseye lantern (unf)]] is boostable. Adding it to a [[Bullseye lantern (empty)]] or [[Bullseye lantern]] is not boostable.</ref>',
        "required_to_start": "NO",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "ALL_OF",
                    children=(
                        node(
                            "SKILL_AT_LEAST",
                            skill="crafting",
                            minimum=20,
                            boostable="YES",
                        ),
                        node(
                            "UNRESOLVED_ROUTE",
                            description=(
                                "Add the sapphire lens to an "
                                "unfinished bullseye lantern; "
                                "item and method verification "
                                "not yet implemented."
                            ),
                        ),
                    ),
                ),
                node(
                    "ALL_OF",
                    children=(
                        node(
                            "SKILL_AT_LEAST",
                            skill="crafting",
                            minimum=20,
                            boostable="NO",
                        ),
                        node(
                            "UNRESOLVED_ROUTE",
                            description=(
                                "Add the sapphire lens to an "
                                "empty or completed bullseye "
                                "lantern; item and method "
                                "verification not yet implemented."
                            ),
                        ),
                    ),
                ),
            ),
        ),
    },
    "enakhras_lament": {
        "source_text": '*{{SCP|Firemaking|45|link=yes}} {{Boostable|yes}} {{Questreqstart|no}} {{Refn|Although Firemaking is listed as a requirement, it is only used during the quest to identify what item needs to go in what brazier. Investigating the braziers is not required, meaning that it is possible to just guess and check which item goes in what brazier, so the Firemaking level is not actually required.|group=q}}',
        "required_to_start": "NO",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "SKILL_AT_LEAST",
                    skill="firemaking",
                    minimum=45,
                    boostable="YES",
                ),
                node(
                    "UNRESOLVED_ROUTE",
                    description=(
                        "Identify brazier item placements through "
                        "trial and error instead of using the "
                        "Firemaking skill; mechanics remain "
                        "unverified for eligibility evaluation."
                    ),
                ),
            ),
        ),
    },
    "temple_of_ikov": {
        "source_text": (
            "* {{SCP|Ranged|40|link=yes}} "
            "{{Boostable|no}} {{Questreqstart|no}} - bypassable "
            "<ref>This requirement can be bypassed - "
            "[[Temple_of_Ikov#Fire_Warrior_of_Lesarkus|see below]]"
            "</ref>"
        ),
        "required_to_start": "NO",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "SKILL_AT_LEAST",
                    skill="ranged",
                    minimum=40,
                    boostable="NO",
                ),
                node(
                    "UNRESOLVED_ROUTE",
                    description=(
                        "Bypass of the Ranged requirement "
                        "described in Temple of Ikov; "
                        "mechanics require review."
                    ),
                ),
            ),
        ),
    },
    "elemental_workshop_i": {
        "source_text": (
            "* {{SCP|Mining|20|link=yes}} "
            "{{Boostable|yes}} {{Questreqstart|no}} "
            "{{Refn|This requirement can be bypassed "
            "if another player mines the rock.|group=t}}"
        ),
        "required_to_start": "NO",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "SKILL_AT_LEAST",
                    skill="mining",
                    minimum=20,
                    boostable="YES",
                ),
                node(
                    "UNRESOLVED_ROUTE",
                    description=(
                        "Another player mines the required "
                        "rock; multiplayer dependency not "
                        "yet modelled."
                    ),
                ),
            ),
        ),
    },
    "rum_deal": {
        "source_text": (
            "*{{SCP|Fishing|50|link=yes}} "
            "{{Boostable|yes}} {{Questreqstart|no}} "
            "<ref>Fishing requirement can be bypassed "
            "if obtaining 5 [[Karamthulhu]]s from "
            "[[Zombie swab]]s or "
            "[[Zombie pirate (Braindeath Island)|Zombie pirates]]"
            "</ref>"
        ),
        "required_to_start": "NO",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "SKILL_AT_LEAST",
                    skill="fishing",
                    minimum=50,
                    boostable="YES",
                ),
                node(
                    "UNRESOLVED_ROUTE",
                    description=(
                        "Obtain five Karamthulhus from "
                        "Zombie swabs or Zombie pirates; "
                        "item acquisition not yet modelled."
                    ),
                ),
            ),
        ),
    },
    "while_guthix_sleeps": {
        "source_text": (
            "* Ability to enter the [[Warriors' Guild]] "
            "(the sum of your [[Attack]] and [[Strength]] "
            "must be at or above 130; OR "
            "{{SCP|Attack|99|link=yes}}, OR "
            "{{SCP|Strength|99|link=yes}}) "
            "{{Boostable|no}} {{Questreqstart|}}"
        ),
        "required_to_start": "UNKNOWN",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "SKILL_SUM_AT_LEAST",
                    skills=("attack", "strength"),
                    minimum=130,
                    boostable="NO",
                ),
                node(
                    "SKILL_AT_LEAST",
                    skill="attack",
                    minimum=99,
                    boostable="NO",
                ),
                node(
                    "SKILL_AT_LEAST",
                    skill="strength",
                    minimum=99,
                    boostable="NO",
                ),
            ),
        ),
    },
    "desert_treasure_i": {
        "source_text": (
            "* {{SCP|Slayer|10|link=yes}} "
            "{{Boostable|no}}  {{Questreqstart|no}} "
            "'''or''' the [[gas mask]] from [[Plague City]]"
        ),
        "required_to_start": "NO",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "SKILL_AT_LEAST",
                    skill="slayer",
                    minimum=10,
                    boostable="NO",
                ),
                node(
                    "UNRESOLVED_ROUTE",
                    description=(
                        "Alternative involving a gas mask "
                        "from Plague City; access verification "
                        "not yet implemented."
                    ),
                ),
            ),
        ),
    },
    "roving_elves": {
        "source_text": (
            "* {{SCP|Agility|56|link=yes}} "
            "{{Boostable|yes}} {{Questreqstart|no}}, "
            "unless travelling with a [[charter ship]] "
            "to the elven woods"
        ),
        "required_to_start": "NO",
        "expression": node(
            "ANY_OF",
            children=(
                node(
                    "SKILL_AT_LEAST",
                    skill="agility",
                    minimum=56,
                    boostable="YES",
                ),
                node(
                    "UNRESOLVED_ROUTE",
                    description=(
                        "Travel by charter ship to the elven "
                        "woods; access verification not yet "
                        "implemented."
                    ),
                ),
            ),
        ),
    },
}


def normalise_source_whitespace(value):
    '''Ignore whitespace changes, not wording changes.'''
    return " ".join(value.strip().split())


def extract_curated_alternative_observations(record):
    '''Extract reviewed patterns from one Wiki source record.

    Unknown quests return no observations. Known quests whose
    source wording has changed raise an error for manual review.
    '''
    if not isinstance(record, dict):
        raise TypeError("Source record must be a dictionary.")

    quest_id = record.get("quest_id")

    if quest_id not in CURATED_ALTERNATIVES:
        return []

    if (
        record.get("record_type") != "QUEST"
        or record.get("requirements_status") != "FIELD_PRESENT"
    ):
        raise ValueError(
            f"Unexpected source record status: {quest_id}"
        )

    revision = record.get("wiki_revision")
    raw = record.get("requirements_wikitext")

    if type(revision) is not int or revision < 1:
        raise ValueError(
            f"Invalid Wiki revision for {quest_id}"
        )

    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            f"Missing Wiki requirements for {quest_id}"
        )

    specification = CURATED_ALTERNATIVES[quest_id]
    expected = normalise_source_whitespace(
        specification["source_text"]
    )

    matches = [
        (line_number, line)
        for line_number, line in enumerate(
            raw.splitlines(), 1
        )
        if normalise_source_whitespace(line) == expected
    ]

    if len(matches) != 1:
        raise ValueError(
            "Curated alternative requires source review: "
            f"{quest_id}; matching lines={len(matches)}"
        )

    line_number, source_text = matches[0]

    return [
        RequirementObservation(
            source_quest_id=quest_id,
            wiki_revision=revision,
            line_number=line_number,
            source_text=source_text,
            expression=specification["expression"],
            required_to_start=(
                specification["required_to_start"]
            ),
        )
    ]
