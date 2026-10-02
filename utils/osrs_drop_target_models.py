"""Target profiles for generated OSRS drop tiles.

These profiles deliberately separate point value from raw drop count. A
5-point drop tile does not have to mean "obtain 5 drops"; it can mean a harder
source, rarer group, harder access, or more dangerous content.
"""

from utils.board_generation import canonical_id
from utils.osrs_drop_groups import filter_valid_drop_target_by_point_value


DEFAULT_DROP_TARGET_BY_POINT_VALUE = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
}


DROP_TARGET_PROFILE_BY_GROUP_ID = {
    "zulrah_uniques": {
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 5,
    },
    "vorkath_uniques": {
        1: 1,
        3: 2,
        5: 3,
    },
    "giant_mole_unique": {
        1: 1,
        2: 2,
    },
    "scurrius_unique": {
        1: 1,
    },
    "sarachnis_unique": {
        2: 1,
        4: 2,
    },
    "barrows_brothers_unique": {
        1: 2,
        2: 4,
        3: 6,
        4: 8,
        5: 10,
    },
    "kraken_unique": {
        2: 1,
        4: 2,
    },
    "dagannoth_rex_uniques": {
        2: 1,
        3: 2,
        4: 3,
        5: 4,
    },
    "wilderness_unique": {
        2: 1,
        3: 2,
        4: 3,
        5: 4,
    },
    "wilderness_ring": {
        3: 1,
        4: 2,
        5: 3,
    },
}


def get_drop_target_profile(drop_group_id, fallback=None):
    group_id = canonical_id(
        drop_group_id
    )

    profile = DROP_TARGET_PROFILE_BY_GROUP_ID.get(
        group_id
    )

    if profile is None:
        profile = (
            DEFAULT_DROP_TARGET_BY_POINT_VALUE
            if fallback is None
            else dict(
                fallback
            )
        )

    return {
        point_value: target
        for point_value, target in sorted(
            profile.items()
        )
    }


def get_valid_drop_target_profile(drop_group_id, fallback=None):
    return filter_valid_drop_target_by_point_value(
        drop_group_id,
        get_drop_target_profile(
            drop_group_id,
            fallback=fallback,
        ),
    )
