from utils.osrs_pets import get_osrs_pet_options

from utils.osrs_tile_catalogue_preview import (
    get_curated_tile_catalogue_preview,
    get_curated_tile_catalogue_summary,
)


def test_get_curated_tile_catalogue_summary_uses_current_catalogue():
    summary = get_curated_tile_catalogue_summary()

    assert summary.candidate_count == 12 + len(get_osrs_pet_options())
    assert summary.counts_by_primary_category == {
        "KILLCOUNT": 2,
        "DROP": 2,
        "PET": len(get_osrs_pet_options()),
        "SKILL": 8,
    }


def test_get_curated_tile_catalogue_preview_outputs_readable_summary():
    preview = get_curated_tile_catalogue_preview()

    assert f"Candidate count: {12 + len(get_osrs_pet_options())}" in preview
    assert "By point value: 1: 2, 2: 2, 3: 5, 4: 3" in preview
    assert f"5: {len(get_osrs_pet_options())}" in preview
    assert "Obtain Vorki (5 pts, PET)" in preview
    assert "Obtain Rocky (5 pts, PET)" in preview
    assert "Obtain any pet" not in preview
    assert "Obtain any skilling pet" not in preview
    assert "Gain 500,000 Cooking XP (1 pt, SKILL)" in preview
    assert "Conflicts:" in preview
