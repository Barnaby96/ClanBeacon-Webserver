"""Offline regression tests for OSRS requirement observations.

All assertions use frozen local source snapshots.
No Wiki requests, database writes or eligibility evaluation.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from utils.osrs_alternative_requirement_sources import (
    CURATED_ALTERNATIVES,
    extract_curated_alternative_observations,
)
from utils.osrs_contextual_requirement_sources import (
    SOURCE_SPECS,
    extract_curated_contextual_observations,
)
from utils.osrs_quest_prerequisite_parser import (
    build_quest_title_lookup,
    extract_direct_prerequisite_candidates,
    extract_progression_observations,
)
from utils.osrs_quest_skill_parser import (
    parse_skill_requirements,
)
from utils.osrs_nested_review_reconciliation import (
    KNOWN_NESTED_REFERENCES,
    reconcile_nested_reviews,
)
from utils.osrs_requirement_expressions import (
    RequirementNode,
)


DATA = Path(__file__).resolve().parents[1] / "data"


def load(filename):
    return json.loads(
        (DATA / filename).read_text(encoding="utf-8-sig")
    )


@pytest.fixture(scope="module")
def records():
    return (
        load("osrs_quest_requirements_source_v1.json")[
            "requirements_records"
        ]
        +
        load("osrs_miniquest_requirements_source_v1.json")[
            "requirements_records"
        ]
    )


@pytest.fixture(scope="module")
def by_id(records):
    return {record["quest_id"]: record for record in records}


@pytest.fixture(scope="module")
def lookup():
    return build_quest_title_lookup({
        "quest_entries": (
            load("osrs_quest_catalogue_v1.json")[
                "quest_entries"
            ]
            +
            load("osrs_miniquest_catalogue_v1.json")[
                "miniquest_entries"
            ]
        )
    })


@pytest.fixture(scope="module")
def alternatives(records):
    return {
        observation.source_quest_id: observation
        for record in records
        for observation in (
            extract_curated_alternative_observations(record)
        )
    }


@pytest.fixture(scope="module")
def contextual(records):
    return {
        observation["source_quest_id"]: observation
        for record in records
        for observation in (
            extract_curated_contextual_observations(record)
        )
    }


def test_frozen_record_coverage(records, by_id, lookup):
    assert len(records) == 214
    assert len(by_id) == 214
    assert len(lookup) == 214
    assert set(by_id) == set(lookup.values())


def test_curated_alternative_provenance(
    alternatives, by_id
):
    assert len(CURATED_ALTERNATIVES) == 8
    assert set(alternatives) == set(CURATED_ALTERNATIVES)

    for quest_id, observation in alternatives.items():
        record = by_id[quest_id]

        assert observation.wiki_revision == (
            record["wiki_revision"]
        )
        assert observation.source_text == (
            record["requirements_wikitext"]
            .splitlines()[observation.line_number - 1]
        )
        assert observation.verification_status == "UNVERIFIED"
        assert observation.expression.kind == "ANY_OF"

        exported = observation.to_dict()

        assert exported["verification_status"] == "UNVERIFIED"
        assert json.loads(json.dumps(exported)) == exported


@pytest.mark.parametrize(
    "quest_id,skill,level,boostable",
    [
        ("temple_of_ikov", "ranged", 40, "NO"),
        ("elemental_workshop_i", "mining", 20, "YES"),
        ("rum_deal", "fishing", 50, "YES"),
        ("desert_treasure_i", "slayer", 10, "NO"),
        ("roving_elves", "agility", 56, "YES"),
        ("enakhras_lament", "firemaking", 45, "YES"),
    ],
)
def test_skill_or_unresolved_route(
    alternatives, quest_id, skill, level, boostable
):
    observation = alternatives[quest_id]

    assert observation.required_to_start == "NO"

    branches = observation.expression.children

    assert len(branches) == 2

    skill_route, other_route = branches

    assert skill_route.kind == "SKILL_AT_LEAST"
    assert skill_route.skill == skill
    assert skill_route.minimum == level
    assert skill_route.boostable == boostable

    assert other_route.kind == "UNRESOLVED_ROUTE"
    assert other_route.description


def test_warriors_guild_compound_alternative(alternatives):
    observation = alternatives["while_guthix_sleeps"]

    assert observation.required_to_start == "UNKNOWN"

    branches = observation.expression.children

    assert len(branches) == 3

    combined, attack, strength = branches

    assert combined.kind == "SKILL_SUM_AT_LEAST"
    assert combined.skills == ("attack", "strength")
    assert combined.minimum == 130
    assert combined.boostable == "NO"

    assert (attack.kind, attack.skill, attack.minimum) == (
        "SKILL_AT_LEAST", "attack", 99
    )

    assert (
        strength.kind,
        strength.skill,
        strength.minimum,
    ) == ("SKILL_AT_LEAST", "strength", 99)


def test_tears_of_guthix_method_branches(alternatives):
    observation = alternatives["tears_of_guthix"]

    assert observation.required_to_start == "NO"

    expression = observation.expression

    assert expression.kind == "ANY_OF"
    assert len(expression.children) == 2

    for branch, boostable in zip(
        expression.children, ("YES", "NO")
    ):
        assert branch.kind == "ALL_OF"
        assert len(branch.children) == 2

        skill, method = branch.children

        assert skill.kind == "SKILL_AT_LEAST"
        assert skill.skill == "crafting"
        assert skill.minimum == 20
        assert skill.boostable == boostable

        assert method.kind == "UNRESOLVED_ROUTE"
        assert method.description


def test_contextual_observations(contextual, by_id):
    assert len(SOURCE_SPECS) == 5
    assert set(contextual) == set(SOURCE_SPECS)

    expected_kinds = {
        "tai_bwo_wannai_trio": "OPTIONAL_METHOD_LEVEL",
        "troll_stronghold": "RECOMMENDED_LEVEL",
        "the_fremennik_isles": "LATER_STAGE_REQUIREMENT",
        "grim_tales": "REPEATED_SKILL_CHECK",
        "recipe_for_disaster": "COMBAT_RESTRICTION",
    }

    for quest_id, note in contextual.items():
        record = by_id[quest_id]

        assert note["note_kind"] == expected_kinds[quest_id]
        assert note["verification_status"] == "UNVERIFIED"
        assert note["eligibility_status"] == "NOT_EVALUATED"
        assert note["wiki_revision"] == record["wiki_revision"]
        assert note["source_text"] == (
            record["requirements_wikitext"]
            .splitlines()[note["line_number"] - 1]
        )
        assert json.loads(json.dumps(note)) == note

    assert contextual["tai_bwo_wannai_trio"][
        "advisory_level"
    ] == 65

    assert contextual["troll_stronghold"][
        "advisory_level"
    ] == 47

    rfd = contextual["recipe_for_disaster"]

    assert rfd["scope"] == "PARENT_AGGREGATE"
    assert rfd["listed_skill"] is None
    assert rfd["listed_level"] is None


def test_changed_alternative_source_fails_closed(by_id):
    original = by_id["while_guthix_sleeps"]

    modified = dict(original)

    modified["requirements_wikitext"] = (
        original["requirements_wikitext"].replace(
            "at or above 130",
            "at or above 140",
        )
    )

    assert modified["requirements_wikitext"] != (
        original["requirements_wikitext"]
    )

    with pytest.raises(ValueError):
        extract_curated_alternative_observations(modified)


def test_changed_contextual_source_fails_closed(by_id):
    original = by_id["troll_stronghold"]

    modified = dict(original)

    modified["requirements_wikitext"] = (
        original["requirements_wikitext"].replace(
            "47 is recommended",
            "47 is required",
        )
    )

    assert modified["requirements_wikitext"] != (
        original["requirements_wikitext"]
    )

    with pytest.raises(ValueError):
        extract_curated_contextual_observations(modified)


def test_progression_observation_coverage(records, lookup):
    results = [
        extract_progression_observations(
            record["quest_id"],
            record["requirements_wikitext"],
            lookup,
        )
        for record in records
    ]

    observations = [
        item
        for result in results
        for item in result["progression_observations"]
    ]

    context_notes = [
        item
        for result in results
        for item in result["context_notes"]
    ]

    non_quest_notes = [
        item
        for result in results
        for item in result["non_quest_context_notes"]
    ]

    unresolved = [
        item
        for result in results
        for item in result["review_items"]
    ]

    assert len(observations) == 10
    assert len(context_notes) == 1
    assert len(non_quest_notes) == 4
    assert not unresolved

    assert Counter(
        item["progression_kind"]
        for item in observations
    ) == {
        "STARTED": 6,
        "PARTIAL": 2,
        "MILESTONE": 2,
    }

    assert Counter(
        item["context_kind"]
        for item in observations
    ) == {
        "DIRECT": 5,
        "DIRECT_ACCESS": 2,
        "TRANSITIVE": 2,
        "PARENT_AGGREGATE": 1,
    }

    assert Counter(
        item["note_kind"]
        for item in non_quest_notes
    ) == {
        "NON_QUEST_CONDITION_CANDIDATE": 3,
        "OPTIONAL_RECOMMENDATION": 1,
    }

    assert all(
        item["verification_status"] == "UNVERIFIED"
        for item in observations
    )


def test_unknown_progression_target_remains_reviewable(lookup):
    result = extract_progression_observations(
        "synthetic_test",
        "*Started [[An Imaginary Unknown Quest]]",
        lookup,
    )

    assert not result["progression_observations"]
    assert not result["non_quest_context_notes"]
    assert len(result["review_items"]) == 1



def test_vale_totems_plural_completion_heading(by_id, lookup):
    """The plural Wiki heading must produce one direct dependency."""
    vale = by_id["miniquest_vale_totems"]

    result = extract_direct_prerequisite_candidates(
        "miniquest_vale_totems",
        vale["requirements_wikitext"],
        lookup,
    )

    assert len(result["direct_candidates"]) == 1
    assert not result["direct_review"]
    assert not result["other_nested_review"]

    candidate = result["direct_candidates"][0]

    assert candidate == {
        "target_quest_id": "children_of_the_sun",
        "line_number": 2,
        "source_heading": (
            "Completions of the following quests:"
        ),
        "source_text": (
            vale["requirements_wikitext"].splitlines()[1]
        ),
        "verification_status": "UNVERIFIED",
    }

    # The Fractured Archive only directly requires
    # While Guthix Sleeps. Its nested quest list is inherited.
    archive = by_id["miniquest_the_fractured_archive"]

    archive_result = extract_direct_prerequisite_candidates(
        "miniquest_the_fractured_archive",
        archive["requirements_wikitext"],
        lookup,
    )

    assert len(archive_result["direct_candidates"]) == 1
    assert archive_result["direct_candidates"][0][
        "target_quest_id"
    ] == "while_guthix_sleeps"

    # The 46 nested Wiki references are inherited through
    # While Guthix Sleeps, not additional direct prerequisites.
    assert not archive_result["other_nested_review"]

    inherited = archive_result[
        "inherited_prerequisite_observations"
    ]

    assert len(inherited) == 46
    assert archive_result["transitive_lines"] == 46

    assert {
        item["line_number"]
        for item in inherited
    } == set(range(3, 49))

    archive_lines = (
        archive["requirements_wikitext"].splitlines()
    )

    for item in inherited:
        assert item["inherited_via_quest_id"] == (
            "while_guthix_sleeps"
        )
        assert item["depth"] >= 2
        assert item["verification_status"] == "UNVERIFIED"
        assert item["target_quest_id"] in lookup.values()
        assert item["source_text"] == (
            archive_lines[item["line_number"] - 1]
        )

    # Previously unknown quest links must stay reviewable.
    modified = archive["requirements_wikitext"].replace(
        "**[[Defender of Varrock]]",
        "**[[Entirely Imaginary Quest]]",
        1,
    )

    assert modified != archive["requirements_wikitext"]

    changed = extract_direct_prerequisite_candidates(
        "miniquest_the_fractured_archive",
        modified,
        lookup,
    )

    assert len(changed["direct_candidates"]) == 1
    assert changed["direct_candidates"][0][
        "target_quest_id"
    ] == "while_guthix_sleeps"

    assert len(
        changed["inherited_prerequisite_observations"]
    ) == 45

    assert len(changed["other_nested_review"]) == 1




def test_nested_reconciliation_coverage(records, lookup):
    """Every known nested review must match an existing observation."""
    cases = {}
    unresolved = []
    original_nested = 0
    total_direct = 0
    total_inherited = 0

    for record in records:
        quest_id = record["quest_id"]
        raw = record["requirements_wikitext"]

        prerequisites = extract_direct_prerequisite_candidates(
            quest_id, raw, lookup
        )

        progression = extract_progression_observations(
            quest_id, raw, lookup
        )

        skills = parse_skill_requirements(quest_id, raw)

        reconciled = reconcile_nested_reviews(
            quest_id, prerequisites, progression, skills
        )

        original_nested += len(
            prerequisites["other_nested_review"]
        )

        total_direct += len(
            prerequisites["direct_candidates"]
        )

        total_inherited += len(
            prerequisites["inherited_prerequisite_observations"]
        )

        unresolved.extend(
            reconciled["unresolved_nested_reviews"]
        )

        for item in reconciled["linked_observations"]:
            key = (quest_id, item["line_number"])
            assert key not in cases
            cases[key] = item

    assert original_nested == 5
    assert total_direct == 268
    assert total_inherited == 46
    assert not unresolved

    assert len(KNOWN_NESTED_REFERENCES) == 5
    assert set(cases) == set(KNOWN_NESTED_REFERENCES)

    assert Counter(
        item["observation_kind"]
        for item in cases.values()
    ) == {
        "QUEST_PROGRESSION": 3,
        "OPTIONAL_RECOMMENDATION": 1,
        "NESTED_SKILL_CONDITION": 1,
    }

    for key, item in cases.items():
        specification = KNOWN_NESTED_REFERENCES[key]

        assert item["source_text"] == (
            specification["source_text"]
        )
        assert item["observation_kind"] == (
            specification["kind"]
        )
        assert item["observation"]["source_text"] == (
            item["source_text"]
        )
        assert item["verification_status"] == "UNVERIFIED"
        assert item["eligibility_status"] == "NOT_EVALUATED"

    for key in (
        ("ratcatchers", 6),
        ("recipe_for_disaster_freeing_sir_amik_varze", 3),
    ):
        assert cases[key]["observation"]["context_kind"] == (
            "DIRECT_ACCESS"
        )

    shadow = cases[
        ("miniquest_the_generals_shadow", 2)
    ]

    assert shadow["observation"]["context_kind"] == (
        "TRANSITIVE"
    )

    advice = cases[("my_arms_big_adventure", 11)]

    assert advice["observation"]["note_kind"] == (
        "OPTIONAL_RECOMMENDATION"
    )

    curse = cases[
        ("miniquest_curse_of_the_empty_lord", 2)
    ]

    assert curse["observation"]["skill"] == "thieving"
    assert curse["observation"]["level"] == 53
    assert curse["observation"][
        "required_to_start"
    ] == "yes"


def test_nested_reconciliation_fails_closed(by_id, lookup):
    """Missing, modified and unknown observations must stay reviewable."""
    quest_id = "ratcatchers"
    raw = by_id[quest_id]["requirements_wikitext"]

    prerequisites = extract_direct_prerequisite_candidates(
        quest_id, raw, lookup
    )

    progression = extract_progression_observations(
        quest_id, raw, lookup
    )

    skills = parse_skill_requirements(quest_id, raw)

    assert len(prerequisites["other_nested_review"]) == 1

    original_item = prerequisites["other_nested_review"][0]

    # Modifying an audited source line must prevent reconciliation.
    changed = {
        **prerequisites,
        "other_nested_review": [{
            **original_item,
            "source_text": (
                original_item["source_text"] + " changed"
            ),
        }],
    }

    result = reconcile_nested_reviews(
        quest_id, changed, progression, skills
    )

    assert not result["linked_observations"]
    assert len(result["unresolved_nested_reviews"]) == 1
    assert result["unresolved_nested_reviews"][0][
        "reason"
    ] == "AUDITED_SOURCE_CHANGED"

    # Even unchanged wording is insufficient without an
    # independently extracted, matching observation.
    missing = reconcile_nested_reviews(
        quest_id,
        prerequisites,
        {
            **progression,
            "progression_observations": [],
        },
        skills,
    )

    assert not missing["linked_observations"]
    assert len(missing["unresolved_nested_reviews"]) == 1
    assert missing["unresolved_nested_reviews"][0][
        "reason"
    ] == "MATCHING_OBSERVATION_UNAVAILABLE"

    # Unrecognised references cannot be silently accepted.
    unknown = reconcile_nested_reviews(
        "synthetic_quest",
        {
            "other_nested_review": [{
                "line_number": 2,
                "source_text": "**[[Imaginary Quest]]",
                "heading": "Unknown requirements",
            }],
        },
        {
            "progression_observations": [],
            "non_quest_context_notes": [],
        },
        {"skills": []},
    )

    assert not unknown["linked_observations"]
    assert len(unknown["unresolved_nested_reviews"]) == 1
    assert unknown["unresolved_nested_reviews"][0][
        "reason"
    ] == "UNCLASSIFIED_NESTED_REFERENCE"




def test_dream_mentor_combat_level_observation(records, by_id):
    """Combat level is a separate, reviewable requirement."""
    record = by_id["dream_mentor"]

    assert record["wiki_revision"] == 15350904

    parsed = parse_skill_requirements(
        "dream_mentor",
        record["requirements_wikitext"],
    )

    assert len(parsed["combat_levels"]) == 1

    combat = parsed["combat_levels"][0]

    assert combat["stat"] == "combat_level"
    assert combat["level"] == 85
    assert combat["required_to_start"] == "yes"
    assert combat["boostable"] == "unknown"
    assert combat["line_number"] == 1
    assert combat["verification_status"] == "UNVERIFIED"

    assert combat["source_text"] == (
        record["requirements_wikitext"].splitlines()[0]
    )

    # A combat-level requirement must not be interpreted
    # as an ordinary skill or a quest-point requirement.
    assert not any(
        item["skill"] == "combat"
        for item in parsed["skills"]
    )

    assert not any(
        item["level"] == 85
        for item in parsed["quest_points"]
    )

    # The existing review flag is intentionally preserved.
    assert any(
        item["type"] == "COMBAT_LEVEL"
        and item["line_number"] == 1
        and item["source_text"] == combat["source_text"]
        for item in parsed["review_items"]
    )

    # Confirm combat-level observations are not being
    # accidentally created for other quests or miniquests.
    all_combat = [
        (source_record["quest_id"], item)
        for source_record in records
        for item in parse_skill_requirements(
            source_record["quest_id"],
            source_record["requirements_wikitext"],
        )["combat_levels"]
    ]

    assert len(all_combat) == 1
    assert all_combat[0][0] == "dream_mentor"
    assert all_combat[0][1] == combat

    # The observation must be serialisable without losing
    # its source, timing or verification information.
    assert json.loads(json.dumps(combat)) == combat




def test_dorgeshuun_quest_start_annotation(by_id, records):
    """A trailing empty Questreqstart argument is harmless."""
    record = by_id["death_to_the_dorgeshuun"]

    assert record["wiki_revision"] == 15373692

    parsed = parse_skill_requirements(
        record["quest_id"],
        record["requirements_wikitext"],
    )

    agility = [
        item
        for item in parsed["skills"]
        if item["skill"] == "agility"
        and item["level"] == 23
    ]

    assert len(agility) == 1

    requirement = agility[0]

    assert requirement["boostable"] == "yes"
    assert requirement["required_to_start"] == "no"
    assert requirement["line_number"] == 5
    assert requirement["verification_status"] == "UNVERIFIED"

    assert requirement["source_text"] == (
        record["requirements_wikitext"].splitlines()[4]
    )

    assert "{{Questreqstart|no|}}" in (
        requirement["source_text"]
    )

    assert not any(
        item["type"] == "UNUSUAL_QUESTREQSTART"
        for item in parsed["review_items"]
    )

    # Protect the complete frozen review count, not just
    # the one corrected quest.
    review_counts = Counter(
        issue["type"]
        for source_record in records
        for issue in parse_skill_requirements(
            source_record["quest_id"],
            source_record["requirements_wikitext"],
        )["review_items"]
    )

    assert review_counts == {
        "COMBAT_LEVEL": 1,
        "COMPOUND_SCP": 1,
        "NON_NUMERIC_SCP": 4,
        "UNUSUAL_BOOSTABLE": 1,
    }


def test_quest_start_annotation_variants_fail_closed():
    """Only one trailing empty argument may be tolerated."""
    cases = [
        ("no", "no", False),
        ("yes", "yes", False),
        ("no|", "no", False),
        ("yes|", "yes", False),
        ("NO|", "no", False),
        ("no|extra", "unknown", True),
        ("yes|no", "unknown", True),
        ("no||", "unknown", True),
        ("", "unknown", False),
    ]

    for raw, expected, expect_review in cases:
        line = (
            "*{{SCP|Agility|23}} "
            "{{Boostable|yes}} "
            "{{Questreqstart|" + raw + "}}"
        )

        parsed = parse_skill_requirements(
            "synthetic_quest", line
        )

        assert len(parsed["skills"]) == 1
        assert parsed["skills"][0][
            "required_to_start"
        ] == expected

        has_review = any(
            item["type"] == "UNUSUAL_QUESTREQSTART"
            for item in parsed["review_items"]
        )

        assert has_review == expect_review, raw

    # Multiple conflicting annotations must not
    # resolve to a definite quest-start requirement.
    conflicting = parse_skill_requirements(
        "synthetic_quest",
        "*{{SCP|Agility|23}} "
        "{{Questreqstart|yes}} "
        "{{Questreqstart|no}}",
    )

    assert conflicting["skills"][0][
        "required_to_start"
    ] == "unknown"

    assert any(
        item["type"] == "UNUSUAL_QUESTREQSTART"
        for item in conflicting["review_items"]
    )

    # This formatting tolerance must not spill over
    # into boostability parsing.
    boostable = parse_skill_requirements(
        "synthetic_quest",
        "*{{SCP|Agility|23}} "
        "{{Boostable|no|}} "
        "{{Questreqstart|yes}}",
    )

    assert boostable["skills"][0][
        "boostable"
    ] == "unknown"

    assert boostable["skills"][0][
        "required_to_start"
    ] == "yes"

    assert any(
        item["type"] == "UNUSUAL_BOOSTABLE"
        for item in boostable["review_items"]
    )



def test_original_extraction_counts_unchanged(records, lookup):
    total_skills = 0
    total_points = 0
    total_direct = 0
    conditions = Counter()

    for record in records:
        quest_id = record["quest_id"]
        raw = record["requirements_wikitext"]

        parsed = parse_skill_requirements(quest_id, raw)

        total_skills += len(parsed["skills"])
        total_points += len(parsed["quest_points"])

        conditions.update(
            item["condition_kind"]
            for item in parsed["conditional_skill_lines"]
        )

        prerequisites = (
            extract_direct_prerequisite_candidates(
                quest_id, raw, lookup
            )
        )

        total_direct += len(
            prerequisites["direct_candidates"]
        )

    assert total_skills == 390
    assert total_points == 14
    assert total_direct == 268

    assert conditions == {
        "ALTERNATIVE": 3,
        "BYPASSABLE": 3,
        "COMMENT_ONLY": 1,
        "COMPOUND_ALTERNATIVE": 1,
        "CONTEXTUAL_REVIEW": 7,
    }


def test_requirement_model_rejects_invalid_nodes():
    invalid = (
        lambda: RequirementNode(
            kind="ANY_OF",
            children=(),
        ),
        lambda: RequirementNode(
            kind="SKILL_AT_LEAST",
            skill="imaginary_skill",
            minimum=10,
        ),
        lambda: RequirementNode(
            kind="SKILL_AT_LEAST",
            skill="magic",
            minimum=True,
        ),
        lambda: RequirementNode(
            kind="UNRESOLVED_ROUTE",
            description="",
        ),
    )

    for factory in invalid:
        with pytest.raises((ValueError, TypeError)):
            factory()
