from collections import Counter

from utils.board_generation import TileCategory
from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates


def test_curated_generation_catalogue_uses_generated_drop_pool():
    candidates = get_curated_tile_generation_candidates()
    counts = Counter(candidate.primary_category for candidate in candidates)

    assert counts[TileCategory.DROP] == 410

    drop_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.primary_category == TileCategory.DROP
    )

    assert any(
        candidate.routes[0].drop_id is not None
        for candidate in drop_candidates
    )
    assert any(
        candidate.routes[0].drop_id is None
        for candidate in drop_candidates
    )
