from utils.board_generation import TileCategory
from utils.osrs_tile_catalogue import get_curated_tile_candidates
from utils.osrs_tile_catalogue_validation import (
    build_candidate_requirement_summary,
    build_catalogue_summary,
    find_candidate_conflicts,
    format_catalogue_summary,
    format_skill_requirements,
)


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
        "Obtain any Zulrah unique",
    )
    assert conflict_lookup["boss:zulrah"] == (
        "Complete 150 Zulrah KC",
        "Obtain any Zulrah unique",
    )
    assert conflict_lookup["source:vorkath"] == (
        "Complete 150 Vorkath KC",
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

    assert summary.candidate_count == 14
    assert summary.counts_by_point_value == {
        1: 2,
        2: 2,
        3: 5,
        4: 4,
        5: 1,
    }
    assert summary.counts_by_primary_category == {
        "KILLCOUNT": 2,
        "DROP": 2,
        "PET": 2,
        "SKILL": 8,
    }
    assert len(summary.requirement_summaries) == 14
    assert {
        conflict.tag
        for conflict in summary.conflicts
    } == {
        "boss:vorkath",
        "boss:zulrah",
        "source:any_pet",
        "source:vorkath",
        "source:zulrah",
    }


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

    assert "Candidate count: 14" in preview
    assert "By point value: 1: 2, 2: 2, 3: 5, 4: 4, 5: 1" in preview
    assert "By primary category: DROP: 2, KILLCOUNT: 2, PET: 2, SKILL: 8" in preview

    assert "Complete 150 Zulrah KC (3 pts, KILLCOUNT)" in preview
    assert "Tags: boss:zulrah, metric:boss_zulrah_kc, source:zulrah" in preview
    assert "Effective skills: Agility 56, Crafting 10, Ranged 25" in preview
    assert "Access flags: QUEST_LOCKED" in preview

    assert "Conflicts:" in preview
    assert (
        "source:zulrah: Complete 150 Zulrah KC | Obtain any Zulrah unique"
        in preview
    )
