"""Expand tile templates into generated board candidates."""

from dataclasses import dataclass

from utils.board_generation import (
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
    canonical_id,
)

from utils.osrs_tile_templates import (
    make_drop_candidate,
    make_killcount_candidate,
    make_skill_xp_candidate,
)


VALID_POINT_VALUES = frozenset(
    range(1, 6)
)


def normalise_target_by_point_value(target_by_point_value):
    if hasattr(target_by_point_value, "items"):
        items = target_by_point_value.items()
    else:
        items = target_by_point_value

    normalised = []

    for point_value, target in items:
        point_value = int(point_value)
        target = int(target)

        if point_value not in VALID_POINT_VALUES:
            raise ValueError(
                "Killcount point values must be between 1 and 5."
            )

        if target <= 0:
            raise ValueError(
                "Killcount targets must be positive."
            )

        normalised.append(
            (point_value, target)
        )

    if not normalised:
        raise ValueError(
            "Killcount templates require at least one target."
        )

    return tuple(
        sorted(
            normalised
        )
    )


@dataclass(frozen=True)
class KillcountTileTemplate:
    source_name: str
    boss_id: str
    target_by_point_value: tuple
    content_id: str | None = None
    rng_level: int = 0
    explanation: tuple = ()

    def __post_init__(self):
        object.__setattr__(
            self,
            "target_by_point_value",
            normalise_target_by_point_value(
                self.target_by_point_value
            )
        )


def format_killcount_title(source_name, target):
    return f"Complete {target:,} {source_name} KC"


def expand_killcount_template(template):
    return tuple(
        make_killcount_candidate(
            title=format_killcount_title(
                template.source_name,
                target
            ),
            point_value=point_value,
            boss_id=template.boss_id,
            target=target,
            content_id=template.content_id,
            display_text=format_killcount_title(
                template.source_name,
                target
            ),
            rng_level=template.rng_level,
            explanation=(
                *template.explanation,
                (
                    f"Generated {point_value}-point killcount target "
                    f"from the {template.source_name} template."
                ),
            ),
        )
        for point_value, target in template.target_by_point_value
    )


def normalise_drop_target_by_point_value(target_by_point_value):
    if hasattr(target_by_point_value, "items"):
        items = target_by_point_value.items()
    else:
        items = target_by_point_value

    normalised = []

    for point_value, target in items:
        point_value = int(point_value)
        target = int(target)

        if point_value not in VALID_POINT_VALUES:
            raise ValueError(
                "Drop point values must be between 1 and 5."
            )

        if target <= 0:
            raise ValueError(
                "Drop targets must be positive."
            )

        normalised.append(
            (point_value, target)
        )

    if not normalised:
        raise ValueError(
            "Drop templates require at least one target."
        )

    return tuple(
        sorted(
            normalised
        )
    )


@dataclass(frozen=True)
class DropTileTemplate:
    source_name: str
    source_id: str
    drop_group_id: str
    target_by_point_value: tuple
    boss_id: str | None = None
    content_id: str | None = None
    rng_level: int = 2
    explanation: tuple = ()

    def __post_init__(self):
        object.__setattr__(
            self,
            "target_by_point_value",
            normalise_drop_target_by_point_value(
                self.target_by_point_value
            )
        )


def format_drop_title(source_name, target):
    noun = "unique" if target == 1 else "uniques"

    return f"Obtain {target:,} {source_name} {noun}"


def expand_drop_template(template):
    return tuple(
        make_drop_candidate(
            title=format_drop_title(
                template.source_name,
                target
            ),
            point_value=point_value,
            source_id=template.source_id,
            target=target,
            drop_group_id=template.drop_group_id,
            boss_id=template.boss_id,
            content_id=template.content_id,
            display_text=format_drop_title(
                template.source_name,
                target
            ),
            rng_level=template.rng_level,
            explanation=(
                *template.explanation,
                (
                    f"Generated {point_value}-point drop target "
                    f"from the {template.source_name} template."
                ),
            ),
        )
        for point_value, target in template.target_by_point_value
    )


def normalise_skill_xp_target_by_point_value(target_by_point_value):
    if hasattr(target_by_point_value, "items"):
        items = target_by_point_value.items()
    else:
        items = target_by_point_value

    normalised = []

    for point_value, xp_target in items:
        point_value = int(point_value)
        xp_target = int(xp_target)

        if point_value not in VALID_POINT_VALUES:
            raise ValueError(
                "Skill XP point values must be between 1 and 5."
            )

        if xp_target <= 0:
            raise ValueError(
                "Skill XP targets must be positive."
            )

        normalised.append(
            (point_value, xp_target)
        )

    if not normalised:
        raise ValueError(
            "Skill XP templates require at least one target."
        )

    return tuple(
        sorted(
            normalised
        )
    )


@dataclass(frozen=True)
class SkillXpTileTemplate:
    skill_name: str
    skill_id: str
    target_by_point_value: tuple
    rng_level: int = 0
    explanation: tuple = ()

    def __post_init__(self):
        object.__setattr__(
            self,
            "target_by_point_value",
            normalise_skill_xp_target_by_point_value(
                self.target_by_point_value
            )
        )


def format_skill_xp_title(skill_name, xp_target):
    return f"Gain {xp_target:,} {skill_name} XP"


def expand_skill_xp_template(template):
    return tuple(
        make_skill_xp_candidate(
            title=format_skill_xp_title(
                template.skill_name,
                xp_target
            ),
            point_value=point_value,
            skill_id=template.skill_id,
            xp_target=xp_target,
            display_text=format_skill_xp_title(
                template.skill_name,
                xp_target
            ),
            rng_level=template.rng_level,
            explanation=(
                *template.explanation,
                (
                    f"Generated {point_value}-point skill XP target "
                    f"from the {template.skill_name} template."
                ),
            ),
        )
        for point_value, xp_target in template.target_by_point_value
    )


def normalise_metric_target_by_point_value(target_by_point_value):
    if hasattr(target_by_point_value, "items"):
        items = target_by_point_value.items()
    else:
        items = target_by_point_value

    normalised = []

    for point_value, target in items:
        point_value = int(point_value)
        target = int(target)

        if point_value not in VALID_POINT_VALUES:
            raise ValueError(
                "Metric point values must be between 1 and 5."
            )

        if target <= 0:
            raise ValueError(
                "Metric targets must be positive."
            )

        normalised.append(
            (point_value, target)
        )

    if not normalised:
        raise ValueError(
            "Metric templates require at least one target."
        )

    return tuple(
        sorted(
            normalised
        )
    )


@dataclass(frozen=True)
class MetricTileTemplate:
    display_name: str
    metric_id: str
    source_id: str
    target_by_point_value: tuple
    activity_group_id: str | None = None
    rng_level: int = 0
    explanation: tuple = ()

    def __post_init__(self):
        object.__setattr__(
            self,
            "target_by_point_value",
            normalise_metric_target_by_point_value(
                self.target_by_point_value
            )
        )


def format_metric_title(display_name, target):
    return f"Complete {target:,} {display_name}"


def build_metric_hard_unique_tags(template):
    tags = []

    if template.activity_group_id:
        tags.append(
            f"activity_group:{canonical_id(template.activity_group_id)}"
        )

    return frozenset(
        tags
    )


def expand_metric_template(template):
    metric_id = canonical_id(
        template.metric_id
    )
    source_id = canonical_id(
        template.source_id
    )

    return tuple(
        TileCandidate(
            title=format_metric_title(
                template.display_name,
                target
            ),
            point_value=point_value,
            primary_category=TileCategory.HYBRID,
            route_mode=RouteMode.SINGLE,
            routes=[
                Route(
                    route_type=TileCategory.HYBRID,
                    display_text=format_metric_title(
                        template.display_name,
                        target
                    ),
                    target=target,
                    tracking_source=TrackingSource.WOM,
                    contribution_mode=ContributionMode.TEAM_SUM,
                    metric_id=metric_id,
                    source_id=source_id,
                    hard_unique_tags=build_metric_hard_unique_tags(
                        template
                    ),
                )
            ],
            rng_level=template.rng_level,
            explanation=(
                *template.explanation,
                (
                    f"Generated {point_value}-point WOM metric target "
                    f"from the {template.display_name} template."
                ),
            ),
        )
        for point_value, target in template.target_by_point_value
    )


STATIC_KILLCOUNT_TEMPLATES = (
    KillcountTileTemplate(
        source_name="Zulrah",
        boss_id="zulrah",
        content_id="zulrah",
        target_by_point_value={
            1: 50,
            2: 100,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Static fallback targets until WOM-based scaling is added.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Vorkath",
        boss_id="vorkath",
        content_id="vorkath",
        target_by_point_value={
            1: 25,
            2: 75,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Static fallback targets until WOM-based scaling is added.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Giant Mole",
        boss_id="giant_mole",
        target_by_point_value={
            1: 25,
            2: 75,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Scurrius",
        boss_id="scurrius",
        target_by_point_value={
            1: 50,
            2: 100,
            3: 200,
            4: 350,
            5: 500,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Sarachnis",
        boss_id="sarachnis",
        target_by_point_value={
            1: 25,
            2: 75,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Barrows",
        boss_id="barrows_chests",
        target_by_point_value={
            1: 25,
            2: 75,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Kraken",
        boss_id="kraken",
        target_by_point_value={
            1: 50,
            2: 150,
            3: 300,
            4: 500,
            5: 750,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Dagannoth Rex",
        boss_id="dagannoth_rex",
        target_by_point_value={
            1: 25,
            2: 75,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Calvar'ion",
        boss_id="calvarion",
        target_by_point_value={
            1: 25,
            2: 75,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    KillcountTileTemplate(
        source_name="Artio",
        boss_id="artio",
        target_by_point_value={
            1: 25,
            2: 75,
            3: 150,
            4: 250,
            5: 400,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
)


STATIC_METRIC_TEMPLATES = (
    MetricTileTemplate(
        display_name="Guardians of the Rift completions",
        metric_id="guardians_of_the_rift_completions",
        source_id="guardians_of_the_rift",
        target_by_point_value={
            1: 25,
            2: 50,
            3: 100,
            4: 175,
            5: 250,
        },
        explanation=(
            "Prototype WOM-backed activity metric.",
        ),
    ),
    MetricTileTemplate(
        display_name="Tempoross completions",
        metric_id="tempoross_completions",
        source_id="tempoross",
        target_by_point_value={
            1: 25,
            2: 50,
            3: 100,
            4: 175,
            5: 250,
        },
        explanation=(
            "Prototype WOM-backed activity metric.",
        ),
    ),
    MetricTileTemplate(
        display_name="Wintertodt kills",
        metric_id="wintertodt_kills",
        source_id="wintertodt",
        target_by_point_value={
            1: 25,
            2: 50,
            3: 100,
            4: 175,
            5: 250,
        },
        explanation=(
            "Prototype WOM-backed activity metric.",
        ),
    ),
    MetricTileTemplate(
        display_name="medium-or-harder clue scrolls",
        metric_id="clue_scrolls_medium_plus_completed",
        source_id="clue_scrolls_medium_plus",
        activity_group_id="clue_scrolls",
        target_by_point_value={
            1: 10,
            2: 25,
            3: 50,
            4: 80,
            5: 120,
        },
        explanation=(
            "Prototype WOM-backed clue metric.",
            "Shares the clue-scroll activity group to limit clue tiles per board.",
        ),
    ),
    MetricTileTemplate(
        display_name="hard clue scrolls",
        metric_id="clue_scrolls_hard_completed",
        source_id="clue_scrolls_hard",
        activity_group_id="clue_scrolls",
        target_by_point_value={
            1: 5,
            2: 15,
            3: 30,
            4: 50,
            5: 75,
        },
        explanation=(
            "Prototype WOM-backed clue metric.",
            "Shares the clue-scroll activity group to limit clue tiles per board.",
        ),
    ),
    MetricTileTemplate(
        display_name="elite clue scrolls",
        metric_id="clue_scrolls_elite_completed",
        source_id="clue_scrolls_elite",
        activity_group_id="clue_scrolls",
        target_by_point_value={
            1: 2,
            2: 5,
            3: 10,
            4: 15,
            5: 25,
        },
        explanation=(
            "Prototype WOM-backed clue metric.",
            "Shares the clue-scroll activity group to limit clue tiles per board.",
        ),
    ),
)


STATIC_SKILL_XP_TARGETS = {
    1: 250_000,
    2: 500_000,
    3: 750_000,
    4: 1_000_000,
    5: 1_500_000,
}


STATIC_SKILL_XP_TEMPLATES = (
    SkillXpTileTemplate("Cooking", "cooking", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Firemaking", "firemaking", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Fletching", "fletching", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Crafting", "crafting", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Thieving", "thieving", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Fishing", "fishing", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Mining", "mining", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Runecraft", "runecraft", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Woodcutting", "woodcutting", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Hunter", "hunter", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Agility", "agility", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Herblore", "herblore", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Prayer", "prayer", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Slayer", "slayer", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Smithing", "smithing", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Construction", "construction", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Farming", "farming", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Attack", "attack", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Strength", "strength", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Defence", "defence", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Ranged", "ranged", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Magic", "magic", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Hitpoints", "hitpoints", STATIC_SKILL_XP_TARGETS),
    SkillXpTileTemplate("Sailing", "sailing", STATIC_SKILL_XP_TARGETS),
)


STATIC_DROP_TEMPLATES = (
    DropTileTemplate(
        source_name="Zulrah",
        source_id="zulrah",
        boss_id="zulrah",
        content_id="zulrah",
        drop_group_id="zulrah_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Static fallback targets until drop difficulty scaling is added.",
        ),
    ),
    DropTileTemplate(
        source_name="Vorkath",
        source_id="vorkath",
        boss_id="vorkath",
        content_id="vorkath",
        drop_group_id="vorkath_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Static fallback targets until drop difficulty scaling is added.",
        ),
    ),
    DropTileTemplate(
        source_name="Giant Mole",
        source_id="giant_mole",
        boss_id="giant_mole",
        drop_group_id="giant_mole_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    DropTileTemplate(
        source_name="Scurrius",
        source_id="scurrius",
        boss_id="scurrius",
        drop_group_id="scurrius_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    DropTileTemplate(
        source_name="Sarachnis",
        source_id="sarachnis",
        boss_id="sarachnis",
        drop_group_id="sarachnis_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    DropTileTemplate(
        source_name="Barrows",
        source_id="barrows",
        boss_id="barrows_chests",
        drop_group_id="barrows_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    DropTileTemplate(
        source_name="Kraken",
        source_id="kraken",
        boss_id="kraken",
        drop_group_id="kraken_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    DropTileTemplate(
        source_name="Dagannoth Rex",
        source_id="dagannoth_rex",
        boss_id="dagannoth_rex",
        drop_group_id="dagannoth_rex_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    DropTileTemplate(
        source_name="Calvar'ion",
        source_id="calvarion",
        boss_id="calvarion",
        drop_group_id="calvarion_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
    DropTileTemplate(
        source_name="Artio",
        source_id="artio",
        boss_id="artio",
        drop_group_id="artio_uniques",
        target_by_point_value={
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
        explanation=(
            "Prototype fallback source; access profile to be added later.",
        ),
    ),
)


def get_static_killcount_candidates():
    candidates = []

    for template in STATIC_KILLCOUNT_TEMPLATES:
        candidates.extend(
            expand_killcount_template(
                template
            )
        )

    return tuple(
        candidates
    )


def get_static_drop_candidates():
    candidates = []

    for template in STATIC_DROP_TEMPLATES:
        candidates.extend(
            expand_drop_template(
                template
            )
        )

    return tuple(
        candidates
    )


def get_static_skill_xp_candidates():
    candidates = []

    for template in STATIC_SKILL_XP_TEMPLATES:
        candidates.extend(
            expand_skill_xp_template(
                template
            )
        )

    return tuple(
        candidates
    )


def get_static_metric_candidates():
    candidates = []

    for template in STATIC_METRIC_TEMPLATES:
        candidates.extend(
            expand_metric_template(
                template
            )
        )

    return tuple(
        candidates
    )
