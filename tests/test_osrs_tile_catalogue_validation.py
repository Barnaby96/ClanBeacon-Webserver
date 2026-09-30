from utils.osrs_pets import get_osrs_pet_options

from utils.board_generation import TileCategory
from utils.osrs_tile_catalogue import get_curated_tile_candidates
from utils.osrs_tile_catalogue_validation import (
    build_candidate_requirement_summary,
    build_catalogue_summary,
    find_candidate_conflicts,
    format_catalogue_summary,
    format_skill_requirements,
)


def expected_catalogue_candidate_count():
    return 12 + len(get_osrs_pet_options())


def expected_counts_by_point_value():
    return {
        1: 2,
        2: 2,
        3: 5,
        4: 3,
        5: len(get_osrs_pet_options()),
    }


def expected_counts_by_primary_category():
    return {
        "KILLCOUNT": 2,
        "DROP": 2,
        "PET": len(get_osrs_pet_options()),
        "SKILL": 8,
    }


def test_build_candidate_requirement_summary_includes_requirements_and_tags():
    candidates = {
        candidate.title: candidate
        for candidate in get_curated_tile_candidates()
    }

    summary = build_candidate_requirement_summary(
        candidates["Complete 150 Zulrah KC"]
    )

    assert summary.title == "Complete 150 Zulrah KC"
    assert summary.point_value == 3
    assert summary.primary_category == TileCategory.KILLCOUNT.value
    assert summary.effective_skill_requirements == {
        "agility": 56,
        "ranged": 25,
        "crafting": 10,
    }
    assert summary.recommended_skill_requirements == {}
    assert summary.access_flags == (
        "QUEST_LOCKED",
    )
    assert summary.hard_unique_tags == (
        "boss:zulrah",
        "metric:boss_zulrah_kc",
        "source:zulrah",
    )


def test_find_candidate_conflicts_reports_shared_hard_tags():
    conflicts = find_candidate_conflicts(
        get_curated_tile_candidates()
    )

    conflict_lookup = {
        conflict.tag: conflict.candidate_titles
        for conflict in conflicts
    }

    assert conflict_lookup["source:zulrah"] == (
        "Complete 150 Zulrah KC",
        "Obtain Pet snakeling",
        "Obtain any Zulrah unique",
    )
    assert conflict_lookup["boss:zulrah"] == (
        "Complete 150 Zulrah KC",
        "Obtain any Zulrah unique",
    )
    assert conflict_lookup["source:vorkath"] == (
        "Complete 150 Vorkath KC",
        "Obtain Vorki",
        "Obtain any Vorkath unique",
    )
    assert conflict_lookup["boss:vorkath"] == (
        "Complete 150 Vorkath KC",
        "Obtain any Vorkath unique",
    )


def test_build_catalogue_summary_counts_candidates_by_point_and_category():
    summary = build_catalogue_summary(
        get_curated_tile_candidates()
    )

    assert summary.candidate_count == expected_catalogue_candidate_count()
    assert summary.counts_by_point_value == expected_counts_by_point_value()
    assert summary.counts_by_primary_category == expected_counts_by_primary_category()
    assert len(summary.requirement_summaries) == expected_catalogue_candidate_count()
    conflict_tags = {
        conflict.tag
        for conflict in summary.conflicts
    }

    assert {
        "boss:vorkath",
        "boss:zulrah",
        "source:vorkath",
        "source:zulrah",
        "source:thieving",
        "pet:rocky",
    }.issubset(conflict_tags)
    assert "source:any_pet" not in conflict_tags


def test_format_skill_requirements_outputs_readable_sorted_requirements():
    assert format_skill_requirements(
        {
            "ranged": 25,
            "agility": 56,
            "crafting": 10,
        }
    ) == "Agility 56, Crafting 10, Ranged 25"

    assert format_skill_requirements({}) == "None"


def test_format_catalogue_summary_includes_requirements_tags_and_conflicts():
    summary = build_catalogue_summary(
        get_curated_tile_candidates()
    )

    preview = format_catalogue_summary(
        summary
    )

    assert f"Candidate count: {expected_catalogue_candidate_count()}" in preview
    assert "By point value: 1: 2, 2: 2, 3: 5, 4: 3" in preview
    assert f"5: {len(get_osrs_pet_options())}" in preview
    assert f"PET: {len(get_osrs_pet_options())}" in preview
    assert "DROP: 2" in preview
    assert "KILLCOUNT: 2" in preview
    assert "SKILL: 8" in preview

    assert "Complete 150 Zulrah KC (3 pts, KILLCOUNT)" in preview
    assert "Tags: boss:zulrah, metric:boss_zulrah_kc, source:zulrah" in preview
    assert "Effective skills: Agility 56, Crafting 10, Ranged 25" in preview
    assert "Access flags: QUEST_LOCKED" in preview

    assert "Conflicts:" in preview
    assert (
        "source:zulrah: Complete 150 Zulrah KC | Obtain Pet snakeling | Obtain any Zulrah unique"
        in preview
    )
