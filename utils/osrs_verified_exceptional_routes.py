'''Verified exceptional OSRS quest requirements.

Recognises three explicitly scoped, frozen Wiki requirements.

This module does not approve quests, activate reviews, alter
the curated resolver or verify player inventory/progression.

Non-skill conditions remain genuine requirements even when
assumed satisfied for event-planning purposes.
'''

import hashlib


class VerifiedExceptionalRouteError(ValueError):
    pass


EXCEPTION_SCOPE = {
    "creature_of_fenkenstrain": {
        "revision": 15343497,
        "fingerprint": (
            "a8ee8e00a99b23d4d7d1d48dd4987958"
            "d43a3879ecbebb927b44d8a598a9697e"
        ),
        "line": 2,
        "source_text": (
            "* Partial completion of [[The Restless Ghost]]"
        ),
        "kind": "PARTIAL_QUEST_PROGRESSION",
        "condition_id": "partial_the_restless_ghost",
        "partial_quest_id": "the_restless_ghost",
        "alternative_skill": None,
        "prerequisites": ("priest_in_peril",),
        "wiki_ref": (
            "https://oldschool.runescape.wiki/w/"
            "Creature_of_Fenkenstrain"
        ),
        "finding_code": "VERIFIED_PARTIAL_QUEST_PROGRESSION",
        "condition_detail": (
            "Partial progression through The Restless Ghost "
            "is required, including access to a ghostspeak "
            "amulet. Full completion is not required."
        ),
    },
    "roving_elves": {
        "revision": 15374498,
        "fingerprint": (
            "8a9f7b5e4201b0527743c67f21dce046"
            "040213edab78a8e2fb41f1d320865d25"
        ),
        "line": 8,
        "source_text": (
            "* {{SCP|Agility|56|link=yes}} "
            "{{Boostable|yes}} {{Questreqstart|no}}, "
            "unless travelling with a [[charter ship]] "
            "to the elven woods"
        ),
        "kind": "ALTERNATIVE_SKILL_OR_NON_SKILL",
        "condition_id": "charter_ship_to_elven_woods",
        "partial_quest_id": None,
        "alternative_skill": ("agility", 56, "yes"),
        "prerequisites": ("regicide", "waterfall_quest"),
        "wiki_ref": (
            "https://oldschool.runescape.wiki/w/Roving_Elves"
        ),
        "finding_code": "VERIFIED_ALTERNATIVE_QUEST_ROUTE",
        "condition_detail": (
            "Charter-ship travel is an alternative to the "
            "direct 56 Agility travel requirement. "
            "All inherited Regicide requirements remain."
        ),
    },
    "desert_treasure_i": {
        "revision": 15374595,
        "fingerprint": (
            "510786a8d9ddb4658d6ecfce804d93e"
            "3047531e43a5f4948ffabefa6f400dd9a"
        ),
        "line": 12,
        "source_text": (
            "* {{SCP|Slayer|10|link=yes}} "
            "{{Boostable|no}}  {{Questreqstart|no}} "
            "'''or''' the [[gas mask]] from [[Plague City]]"
        ),
        "kind": "ALTERNATIVE_SKILL_OR_NON_SKILL",
        "condition_id": "gas_mask_from_plague_city",
        "partial_quest_id": None,
        "alternative_skill": ("slayer", 10, "no"),
        "prerequisites": (
            "the_dig_site",
            "temple_of_ikov",
            "the_tourist_trap",
            "troll_stronghold",
            "priest_in_peril",
            "waterfall_quest",
        ),
        "wiki_ref": (
            "https://oldschool.runescape.wiki/w/"
            "Desert_Treasure_I"
        ),
        "finding_code": "VERIFIED_ALTERNATIVE_QUEST_ROUTE",
        "condition_detail": (
            "A gas mask obtained through Plague City is "
            "an alternative to unboostable 10 Slayer. "
            "Gas-mask possession is not verified by WOM. "
            "Plague City is not automatically added as "
            "a completed-quest prerequisite."
        ),
    },
}


def effective_verified_exceptional_requirement(proposal, review):
    '''Derive effective requirements without losing route provenance.

    Returns None if no exception has been supplied. Otherwise
    returns direct skills, direct prerequisites, the original
    alternative skill route (where applicable), and an explicitly
    unverified non-skill condition.

    This function never establishes player eligibility.
    '''
    exception = review.get("verified_exceptional_requirement")

    if exception is None:
        return None

    quest_id = proposal.get("quest_id")
    rule = EXCEPTION_SCOPE.get(quest_id)

    if rule is None or not isinstance(exception, dict):
        raise VerifiedExceptionalRouteError(
            "Unsupported exceptional quest requirement"
        )

    required_keys = {
        "quest_id",
        "wiki_revision",
        "source_line",
        "source_text",
        "source_wikitext_sha256",
        "condition_kind",
        "condition_id",
        "verification_decision",
        "authorised_by",
        "evidence_refs",
    }

    if set(exception) != required_keys:
        raise VerifiedExceptionalRouteError(
            "Invalid exceptional requirement structure"
        )

    source = proposal.get("requirements_wikitext")

    if (
        proposal.get("requirements_status") != "FIELD_PRESENT"
        or not isinstance(source, str)
    ):
        raise VerifiedExceptionalRouteError(
            "Frozen quest requirements unavailable"
        )

    lines = source.splitlines()
    line_number = rule["line"]
    fingerprint = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()

    if (
        type(proposal.get("wiki_revision")) is not int
        or type(review.get("wiki_revision")) is not int
        or type(exception["wiki_revision"]) is not int
        or type(exception["source_line"]) is not int
        or proposal["wiki_revision"] != rule["revision"]
        or review["wiki_revision"] != rule["revision"]
        or exception["wiki_revision"] != rule["revision"]
        or exception["source_line"] != line_number
        or not 1 <= line_number <= len(lines)
        or lines[line_number - 1] != rule["source_text"]
        or exception["source_text"] != rule["source_text"]
        or fingerprint != rule["fingerprint"]
        or exception["source_wikitext_sha256"] != fingerprint
        or exception["quest_id"] != quest_id
        or review.get("quest_id") != quest_id
        or exception["condition_kind"] != rule["kind"]
        or exception["condition_id"] != rule["condition_id"]
        or exception["verification_decision"]
        != "VERIFIED_EXCEPTIONAL_QUEST_REQUIREMENT"
        or exception["authorised_by"]
        != "CLANBEACON_ORGANISER_STEP_275_32"
    ):
        raise VerifiedExceptionalRouteError(
            "Exceptional requirement source identity mismatch"
        )

    refs = exception["evidence_refs"]
    reviewer_refs = review.get("reviewer_evidence_refs")
    findings = review.get("review_findings")

    if (
        not isinstance(refs, list)
        or refs != [rule["wiki_ref"]]
        or not isinstance(reviewer_refs, list)
        or rule["wiki_ref"] not in reviewer_refs
        or not isinstance(findings, list)
    ):
        raise VerifiedExceptionalRouteError(
            "Independent Wiki evidence missing"
        )

    independent = [
        item for item in findings
        if isinstance(item, dict)
        and item.get("code") == "INDEPENDENT_SOURCE_VERIFICATION"
        and item.get("status") == "RESOLVED"
        and rule["wiki_ref"] in item.get(
            "resolution_evidence_refs", []
        )
    ]

    matching = [
        item for item in findings
        if isinstance(item, dict)
        and item.get("code") == rule["finding_code"]
        and item.get("source_line") == line_number
        and item.get("status") == "RESOLVED"
        and item.get("resolution") == rule["condition_detail"]
        and item.get("resolution_evidence_refs") == refs
    ]

    if len(independent) != 1 or len(matching) != 1:
        raise VerifiedExceptionalRouteError(
            "Missing resolved exceptional requirement finding"
        )

    observations = proposal.get("observations")

    if not isinstance(observations, dict):
        raise VerifiedExceptionalRouteError(
            "Frozen observations unavailable"
        )

    skills = observations.get("skills")
    prerequisites = observations.get("prerequisites")
    progression = observations.get("progression")

    if not all(
        isinstance(value, dict)
        for value in (skills, prerequisites, progression)
    ):
        raise VerifiedExceptionalRouteError(
            "Malformed frozen observations"
        )

    original_skills = skills.get("skills")
    direct_candidates = prerequisites.get("direct_candidates")

    if (
        not isinstance(original_skills, list)
        or not isinstance(direct_candidates, list)
    ):
        raise VerifiedExceptionalRouteError(
            "Malformed direct requirements"
        )

    original_levels = {
        item["skill"]: item["level"]
        for item in original_skills
    }

    original_boostability = {
        item["skill"]: item["boostable"]
        for item in original_skills
    }

    if (
        len(original_levels) != len(original_skills)
        or review.get("proposed_direct_skill_requirements")
        != original_levels
        or tuple(review.get(
            "proposed_direct_prerequisite_quest_ids", ()
        )) != rule["prerequisites"]
        or tuple(
            item["target_quest_id"]
            for item in direct_candidates
        ) != rule["prerequisites"]
    ):
        raise VerifiedExceptionalRouteError(
            "Mandatory requirements do not match frozen source"
        )

    effective_skills = dict(original_levels)
    effective_boostability = dict(original_boostability)
    alternative_skill_route = None

    if rule["kind"] == "PARTIAL_QUEST_PROGRESSION":
        observations_list = progression.get(
            "progression_observations"
        )

        matching_progression = [
            item for item in observations_list
            if item.get("line_number") == line_number
            and item.get("source_text") == rule["source_text"]
            and item.get("progression_kind") == "PARTIAL"
            and item.get("context_kind") == "DIRECT"
            and item.get("target_quest_ids")
            == [rule["partial_quest_id"]]
        ] if isinstance(observations_list, list) else []

        if (
            len(matching_progression) != 1
            or rule["partial_quest_id"] in rule["prerequisites"]
        ):
            raise VerifiedExceptionalRouteError(
                "Partial quest progression mismatch"
            )

    else:
        skill, level, boostability = rule["alternative_skill"]

        matches = [
            item for item in original_skills
            if item.get("skill") == skill
            and item.get("level") == level
            and item.get("boostable") == boostability
            and item.get("line_number") == line_number
            and item.get("source_text") == rule["source_text"]
            and item.get("condition_kind") == "ALTERNATIVE"
            and item.get("needs_condition_review") is True
        ]

        conditional_matches = [
            item for item in skills.get(
                "conditional_skill_lines", []
            )
            if item.get("line_number") == line_number
            and item.get("source_text") == rule["source_text"]
            and item.get("condition_kind") == "ALTERNATIVE"
            and item.get("needs_review") is True
        ]

        if len(matches) != 1 or len(conditional_matches) != 1:
            raise VerifiedExceptionalRouteError(
                "Alternative skill source mismatch"
            )

        alternative_skill_route = {
            "skill": skill,
            "level": level,
            "boostability": boostability,
        }

        del effective_skills[skill]
        del effective_boostability[skill]

    return {
        "quest_id": quest_id,
        "effective_direct_skill_requirements": effective_skills,
        "effective_direct_skill_boostability": effective_boostability,
        "direct_prerequisite_quest_ids": rule["prerequisites"],
        "alternative_skill_route": alternative_skill_route,
        "non_skill_condition": {
            "condition_id": rule["condition_id"],
            "kind": rule["kind"],
            "detail": rule["condition_detail"],
            "evidence_status": "NOT_INDEPENDENTLY_MEASURED",
            "planning_policy": "ASSUMED_FOR_PLANNING_ONLY",
            "partial_quest_id": rule["partial_quest_id"],
        },
        "source_wikitext_sha256": fingerprint,
    }
