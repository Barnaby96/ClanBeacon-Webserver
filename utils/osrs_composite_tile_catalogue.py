"""Curated composite OSRS Bingo tile candidates."""

from utils.osrs_metric_n_of_recipes import (
    build_skilling_minigame_sampler_candidate,
)
from utils.osrs_tile_candidate_validation import assert_valid_tile_candidate_pool


def get_curated_composite_tile_candidates():
    return assert_valid_tile_candidate_pool(
        (
            build_skilling_minigame_sampler_candidate(),
        )
    )
