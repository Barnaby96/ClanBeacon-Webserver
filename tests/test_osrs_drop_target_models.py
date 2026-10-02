from utils.osrs_drop_target_models import (
    get_drop_target_profile,
    get_valid_drop_target_profile,
)


def test_drop_target_profile_can_make_point_value_different_from_drop_count():
    assert get_drop_target_profile(
        "barrows_brothers_unique"
    ) == {
        1: 2,
        2: 4,
        3: 6,
        4: 8,
        5: 10,
    }


def test_drop_target_profile_can_start_at_higher_point_value():
    assert get_drop_target_profile(
        "wilderness_ring"
    ) == {
        3: 1,
        4: 2,
        5: 3,
    }


def test_valid_drop_target_profile_is_capped_by_group_size():
    assert get_valid_drop_target_profile(
        "scurrius_unique"
    ) == {
        1: 1,
    }

    assert get_valid_drop_target_profile(
        "wilderness_ring"
    ) == {
        3: 1,
        4: 2,
        5: 3,
    }


def test_unknown_drop_target_profile_uses_fallback_then_caps():
    assert get_valid_drop_target_profile(
        "unknown_group",
        fallback={
            1: 1,
            2: 2,
        },
    ) == {
        1: 1,
        2: 2,
    }
