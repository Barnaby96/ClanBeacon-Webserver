MAX_WILDERNESS_KC_TILES = 2

WILDERNESS_DROP_GROUP_IDS = frozenset(
    {
        "wildernessunique",
        "wildernessring",
    }
)

WILDERNESS_BOSS_PAIR_BY_NORMALISED_BOSS_ID = {
    "callisto": "callisto_artio",
    "artio": "callisto_artio",
    "vetion": "vetion_calvarion",
    "calvarion": "vetion_calvarion",
    "venenatis": "venenatis_spindel",
    "spindel": "venenatis_spindel",
}


def normalise_encounter_id(value):
    return "".join(
        character
        for character in str(
            value or ""
        ).lower()
        if character.isalnum()
    )


def is_wilderness_drop_group_id(drop_group_id):
    return (
        normalise_encounter_id(
            drop_group_id
        )
        in WILDERNESS_DROP_GROUP_IDS
    )


def get_wilderness_boss_pair_id(boss_id):
    return WILDERNESS_BOSS_PAIR_BY_NORMALISED_BOSS_ID.get(
        normalise_encounter_id(
            boss_id
        )
    )


def get_wilderness_boss_pair_hard_unique_tags(boss_id):
    pair_id = get_wilderness_boss_pair_id(
        boss_id
    )

    if not pair_id:
        return frozenset()

    return frozenset(
        {
            f"wilderness_boss_pair:{pair_id}",
        }
    )
