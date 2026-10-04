from utils.board_generation import TileCategory
from utils.team_balancing import (
    ACTIVITY_BOSS_METRICS,
    CLUE_ACTIVITY_METRICS,
    DT2_BOSS_METRICS,
    ENDGAME_BOSS_METRICS,
    GROUP_BOSS_METRICS,
    MIDGAME_BOSS_METRICS,
    RAID_METRICS,
    SLAYER_BOSS_METRICS,
    SOLO_BOSS_METRICS,
    WILDERNESS_BOSS_METRICS,
)


METRIC_GROUP_CAPABILITY_FIELDS = (
    (
        "solo_boss_score",
        SOLO_BOSS_METRICS,
    ),
    (
        "slayer_boss_score",
        SLAYER_BOSS_METRICS,
    ),
    (
        "dt2_boss_score",
        DT2_BOSS_METRICS,
    ),
    (
        "endgame_boss_score",
        ENDGAME_BOSS_METRICS,
    ),
    (
        "group_boss_score",
        GROUP_BOSS_METRICS,
    ),
    (
        "raid_score",
        RAID_METRICS,
    ),
    (
        "wilderness_boss_score",
        WILDERNESS_BOSS_METRICS,
    ),
    (
        "midgame_boss_score",
        MIDGAME_BOSS_METRICS,
    ),
    (
        "activity_boss_score",
        ACTIVITY_BOSS_METRICS,
    ),
    (
        "clue_activity_score",
        CLUE_ACTIVITY_METRICS,
    ),
)


SPECIAL_CAPABILITY_FIELD_BY_SOURCE_ID = {
    "agility": "skilling_score",
    "farming": "skilling_score",
    "fishing": "skilling_score",
    "herbiboars": "skilling_score",
    "hunter": "skilling_score",
    "hunter_guild_rumours": "skilling_score",
    "mining": "skilling_score",
    "runecraft": "skilling_score",
    "sailing": "skilling_score",
    "thieving": "skilling_score",
    "woodcutting": "skilling_score",
    "wilderness": "wilderness_boss_score",
    "wilderness_unique": "wilderness_boss_score",
    "wilderness_ring": "wilderness_boss_score",
}


CAPABILITY_SOURCE_ID_ALIASES = {
    "barrows": "barrows_chests",
    "ice_inferno": "tzkal_zuk",
    "master_clue_scrolls": "clue_scrolls_master",
    "royal_titans": "the_royal_titans",
    "barrows_brothers": "barrows_chests",
    "barrows_brothers_unique": "barrows_chests",
    "dagannoth_rex_uniques": "dagannoth_rex",
    "giant_mole_unique": "giant_mole",
    "kraken_unique": "kraken",
    "sarachnis_unique": "sarachnis",
    "scurrius_unique": "scurrius",
    "vorkath_uniques": "vorkath",
    "zulrah_uniques": "zulrah",
}


def normalise_capability_source_id(source_id):
    return (
        str(
            source_id or ""
        )
        .strip()
        .casefold()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("'", "")
        .replace("?", "")
    )


CAPABILITY_FIELD_BY_SOURCE_ID = {
    normalise_capability_source_id(
        metric_id
    ): score_field
    for score_field, metric_ids in METRIC_GROUP_CAPABILITY_FIELDS
    for metric_id in metric_ids
}


def iter_capability_source_id_parts(source_id):
    normalised_source_id = normalise_capability_source_id(
        source_id
    )

    if not normalised_source_id:
        return

    yield normalised_source_id

    for separator in (
        "_/_",
        "/",
        ",",
    ):
        if separator in normalised_source_id:
            for source_id_part in normalised_source_id.split(
                separator
            ):
                source_id_part = source_id_part.strip(
                    "_ "
                )

                if source_id_part:
                    yield source_id_part


def get_capability_score_field_for_single_source_id(source_id):
    normalised_source_id = normalise_capability_source_id(
        source_id
    )

    if not normalised_source_id:
        return None

    if normalised_source_id in SPECIAL_CAPABILITY_FIELD_BY_SOURCE_ID:
        return SPECIAL_CAPABILITY_FIELD_BY_SOURCE_ID[
            normalised_source_id
        ]

    aliased_source_id = CAPABILITY_SOURCE_ID_ALIASES.get(
        normalised_source_id,
        normalised_source_id,
    )

    if aliased_source_id in SPECIAL_CAPABILITY_FIELD_BY_SOURCE_ID:
        return SPECIAL_CAPABILITY_FIELD_BY_SOURCE_ID[
            aliased_source_id
        ]

    return CAPABILITY_FIELD_BY_SOURCE_ID.get(
        aliased_source_id
    )


def get_capability_score_field_for_source_id(source_id):
    score_fields = tuple(
        score_field
        for score_field in (
            get_capability_score_field_for_single_source_id(
                source_id_part
            )
            for source_id_part in iter_capability_source_id_parts(
                source_id
            )
        )
        if score_field
    )

    if not score_fields:
        return None

    first_score_field = score_fields[0]

    if all(
        score_field == first_score_field
        for score_field in score_fields
    ):
        return first_score_field

    return None


def get_capability_score_field_for_route(route):
    if route.route_type == TileCategory.SKILL:
        return "skilling_score"

    for source_id in (
        route.boss_id,
        route.source_id,
        route.drop_group_id,
        route.metric_id,
        route.pet_id,
        route.pet_group_id,
    ):
        score_field = get_capability_score_field_for_source_id(
            source_id
        )

        if score_field:
            return score_field

    return None


def get_primary_capability_score_field_for_candidate(candidate):
    route_score_fields = tuple(
        score_field
        for score_field in (
            get_capability_score_field_for_route(
                route
            )
            for route in candidate.routes
        )
        if score_field
    )

    if not route_score_fields:
        return None

    first_score_field = route_score_fields[0]

    if all(
        score_field == first_score_field
        for score_field in route_score_fields
    ):
        return first_score_field

    return None
