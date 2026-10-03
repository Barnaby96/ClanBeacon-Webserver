from types import SimpleNamespace

from utils.board_generation import (
    TileCategory,
    candidate_fits_wilderness_pvm_limits,
)
from utils.osrs_encounter_groups import (
    get_wilderness_boss_pair_hard_unique_tags,
    get_wilderness_boss_pair_id,
    is_wilderness_drop_group_id,
)
from utils.osrs_generation_recipes import build_single_killcount_route


def make_candidate(route_type, boss_id=None, drop_group_id=None):
    return SimpleNamespace(
        routes=(
            SimpleNamespace(
                route_type=route_type,
                boss_id=boss_id,
                drop_group_id=drop_group_id,
            ),
        )
    )


def test_wilderness_boss_pair_ids_are_normalised():
    assert get_wilderness_boss_pair_id("Callisto") == "callisto_artio"
    assert get_wilderness_boss_pair_id("artio") == "callisto_artio"
    assert get_wilderness_boss_pair_id("Vet'ion") == "vetion_calvarion"
    assert get_wilderness_boss_pair_id("calvarion") == "vetion_calvarion"
    assert get_wilderness_boss_pair_id("Venenatis") == "venenatis_spindel"
    assert get_wilderness_boss_pair_id("spindel") == "venenatis_spindel"
    assert get_wilderness_boss_pair_id("zulrah") is None


def test_wilderness_drop_group_ids_are_normalised():
    assert is_wilderness_drop_group_id("wilderness_unique")
    assert is_wilderness_drop_group_id("wilderness_ring")
    assert not is_wilderness_drop_group_id("zulrah_uniques")


def test_wilderness_killcount_routes_get_pair_conflict_tags():
    component = SimpleNamespace(
        boss_id="artio",
        source_id=None,
        metric_id=None,
        display_name="Artio",
        tracking_source="WOM",
        hard_unique_tags=frozenset(),
    )

    route = build_single_killcount_route(
        component,
        75,
    )

    assert route.hard_unique_tags == get_wilderness_boss_pair_hard_unique_tags(
        "artio"
    )


def test_wilderness_pvm_limits_allow_two_different_kc_pairs():
    artio = make_candidate(
        TileCategory.KILLCOUNT,
        boss_id="artio",
    )
    calvarion = make_candidate(
        TileCategory.KILLCOUNT,
        boss_id="calvarion",
    )

    assert candidate_fits_wilderness_pvm_limits(
        calvarion,
        [
            artio,
        ],
    )


def test_wilderness_pvm_limits_block_third_wilderness_kc():
    artio = make_candidate(
        TileCategory.KILLCOUNT,
        boss_id="artio",
    )
    calvarion = make_candidate(
        TileCategory.KILLCOUNT,
        boss_id="calvarion",
    )
    spindel = make_candidate(
        TileCategory.KILLCOUNT,
        boss_id="spindel",
    )

    assert not candidate_fits_wilderness_pvm_limits(
        spindel,
        [
            artio,
            calvarion,
        ],
    )


def test_wilderness_pvm_limits_block_drop_and_kc_mix():
    artio = make_candidate(
        TileCategory.KILLCOUNT,
        boss_id="artio",
    )
    wilderness_drop = make_candidate(
        TileCategory.DROP,
        drop_group_id="wilderness_unique",
    )

    assert not candidate_fits_wilderness_pvm_limits(
        wilderness_drop,
        [
            artio,
        ],
    )
    assert not candidate_fits_wilderness_pvm_limits(
        artio,
        [
            wilderness_drop,
        ],
    )


def test_wilderness_pvm_limits_allow_kc_before_later_drop_slot():
    artio = make_candidate(
        TileCategory.KILLCOUNT,
        boss_id="artio",
    )
    pending_drop_slot = SimpleNamespace(
        is_flex=False,
        required_category=TileCategory.DROP,
    )

    assert candidate_fits_wilderness_pvm_limits(
        artio,
        [],
        pending_slots=(
            pending_drop_slot,
        ),
    )


def test_wilderness_pvm_limits_delay_drop_until_required_killcount_slots_are_handled():
    wilderness_drop = make_candidate(
        TileCategory.DROP,
        drop_group_id="wilderness_unique",
    )
    pending_killcount_slot = SimpleNamespace(
        is_flex=False,
        required_category=TileCategory.KILLCOUNT,
    )

    assert not candidate_fits_wilderness_pvm_limits(
        wilderness_drop,
        [],
        pending_slots=(
            pending_killcount_slot,
        ),
    )
