from utils.osrs_tile_catalogue_preview import (
    get_curated_tile_catalogue_preview,
    get_curated_tile_catalogue_summary,
)


def test_get_curated_tile_catalogue_summary_uses_current_catalogue():
    summary = get_curated_tile_catalogue_summary()

    assert summary.candidate_count == 14
    assert summary.counts_by_primary_category == {
        "KILLCOUNT": 2,
        "DROP": 2,
        "PET": 2,
        "SKILL": 8,
    }


def test_get_curated_tile_catalogue_preview_outputs_readable_summary():
    preview = get_curated_tile_catalogue_preview()

    assert "Candidate count: 14" in preview
    assert "By point value: 1: 2, 2: 2, 3: 5, 4: 4, 5: 1" in preview
    assert "Obtain any skilling pet (4 pts, PET)" in preview
    assert "Gain 500,000 Cooking XP (1 pt, SKILL)" in preview
    assert "Conflicts:" in preview
