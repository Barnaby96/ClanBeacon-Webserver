"""Expand tile templates into generated board candidates."""

from dataclasses import dataclass

from utils.osrs_drop_group_data import DROP_GROUP_DATA

from utils.osrs_drop_groups import get_drop_group_definition
from utils.osrs_drop_target_models import get_valid_drop_target_profile
from utils.osrs_generation_recipes import (
    StaticPointTargetModel,
    build_single_tile_candidate,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)
from utils.osrs_tile_component_expansion import expand_single_component

from utils.board_generation import (
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
    canonical_id,
)

from utils.osrs_tile_templates import access_profile_for_content
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



def format_drop_route_text(source_name, target, drop_group_id=None):
    title = format_drop_title(
        source_name,
        target,
        drop_group_id,
    )

    definition = get_drop_group_definition(
        drop_group_id
    )

    if definition is None:
        return title

    eligible_drop_names = (
        definition.distinct_drop_names
        or definition.drop_names
    )

    if not eligible_drop_names:
        return title

    return (
        f"{title}. Eligible drops: "
        f"{', '.join(eligible_drop_names)}"
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


def build_killcount_component_from_template(template):
    return TileComponent(
        component_id=f"{template.boss_id}_killcount",
        component_type=TileComponentType.KILLCOUNT,
        display_name=template.source_name,
        tracking_source=TrackingSource.WOM,
        target_model_id=f"{template.boss_id}_static_killcount",
        source_id=template.content_id or template.boss_id,
        boss_id=template.boss_id,
        access_profile=access_profile_for_content(
            template.content_id
        ),
        rng_level=template.rng_level,
        notes=template.explanation,
    )


def build_killcount_target_model_from_template(template):
    return StaticPointTargetModel(
        target_model_id=f"{template.boss_id}_static_killcount",
        target_by_point_value=template.target_by_point_value,
    )


def expand_killcount_template(template):
    component = build_killcount_component_from_template(
        template
    )
    target_model = build_killcount_target_model_from_template(
        template
    )

    return expand_single_component(
        component=component,
        target_model=target_model,
        title_formatter=lambda point_value, target: format_killcount_title(
            template.source_name,
            target
        ),
        display_text_formatter=lambda point_value, target: format_killcount_title(
            template.source_name,
            target
        ),
        explanation_formatter=lambda point_value, target: (
            (
                f"Generated {point_value}-point killcount target "
                f"from the {template.source_name} template."
            ),
        ),
        include_generation_note=False,
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


DROP_GROUP_TARGET_LABELS = {
    "wilderness_ring": (
        "Wilderness ring",
        "Wilderness rings",
    ),
}


def format_drop_title(source_name, target, drop_group_id=None):
    labels = DROP_GROUP_TARGET_LABELS.get(
        drop_group_id
    )

    if labels:
        singular, plural = labels
        label = singular if target == 1 else plural

        return f"Obtain {target:,} {label}"

    noun = "unique" if target == 1 else "uniques"

    return f"Obtain {target:,} {source_name} {noun}"


def build_drop_component_from_template(template):
    return TileComponent(
        component_id=f"{template.source_id}_drop",
        component_type=TileComponentType.DROP,
        display_name=f"{template.source_name} uniques",
        tracking_source=TrackingSource.DINK,
        target_model_id=f"{template.source_id}_static_drop",
        source_id=template.source_id,
        boss_id=template.boss_id,
        drop_group_id=template.drop_group_id,
        access_profile=access_profile_for_content(
            template.content_id
        ),
        rng_level=template.rng_level,
        notes=template.explanation,
    )


def build_drop_target_model_from_template(template):
    return StaticPointTargetModel(
        target_model_id=f"{template.source_id}_static_drop",
        target_by_point_value=get_valid_drop_target_profile(
            template.drop_group_id,
            fallback=template.target_by_point_value,
        ),
    )


def expand_drop_template(template):
    component = build_drop_component_from_template(
        template
    )
    target_model = build_drop_target_model_from_template(
        template
    )

    return expand_single_component(
        component=component,
        target_model=target_model,
        title_formatter=lambda point_value, target: format_drop_title(
            template.source_name,
            target,
            template.drop_group_id,
        ),
        display_text_formatter=lambda point_value, target: format_drop_route_text(
            template.source_name,
            target,
            template.drop_group_id,
        ),
        explanation_formatter=lambda point_value, target: (
            (
                f"Generated {point_value}-point drop target "
                f"from the {template.source_name} template."
            ),
        ),
        include_generation_note=False,
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


def build_skill_xp_component_from_template(template):
    return TileComponent(
        component_id=f"{template.skill_id}_experience",
        component_type=TileComponentType.EXPERIENCE,
        display_name=template.skill_name,
        tracking_source=TrackingSource.WOM,
        target_model_id=f"{template.skill_id}_static_experience",
        source_id=template.skill_id,
        skill_id=template.skill_id,
        rng_level=template.rng_level,
        notes=template.explanation,
    )


def build_skill_xp_target_model_from_template(template):
    return StaticPointTargetModel(
        target_model_id=f"{template.skill_id}_static_experience",
        target_by_point_value=template.target_by_point_value,
    )


def expand_skill_xp_template(template):
    component = build_skill_xp_component_from_template(
        template
    )
    target_model = build_skill_xp_target_model_from_template(
        template
    )

    return expand_single_component(
        component=component,
        target_model=target_model,
        title_formatter=lambda point_value, target: format_skill_xp_title(
            template.skill_name,
            target
        ),
        display_text_formatter=lambda point_value, target: format_skill_xp_title(
            template.skill_name,
            target
        ),
        explanation_formatter=lambda point_value, target: (
            (
                f"Generated {point_value}-point skill XP target "
                f"from the {template.skill_name} template."
            ),
        ),
        include_generation_note=False,
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


def build_metric_component_from_template(template):
    groups = ()

    if template.activity_group_id:
        groups = (
            template.activity_group_id,
        )

    return TileComponent(
        component_id=f"{template.metric_id}_metric",
        component_type=TileComponentType.WOM_METRIC,
        display_name=template.display_name,
        tracking_source=TrackingSource.WOM,
        target_model_id=f"{template.metric_id}_static_metric",
        metric_id=template.metric_id,
        source_id=template.source_id,
        groups=groups,
        compatible_recipe_ids=(
            ("SINGLE", "N_OF")
            if groups
            else ("SINGLE",)
        ),
        rng_level=template.rng_level,
        notes=template.explanation,
    )


def build_metric_target_model_from_template(template):
    return StaticPointTargetModel(
        target_model_id=f"{template.metric_id}_static_metric",
        target_by_point_value=template.target_by_point_value,
    )


def expand_metric_template(template):
    component = build_metric_component_from_template(
        template
    )
    target_model = build_metric_target_model_from_template(
        template
    )

    return expand_single_component(
        component=component,
        target_model=target_model,
        title_formatter=lambda point_value, target: format_metric_title(
            template.display_name,
            target
        ),
        display_text_formatter=lambda point_value, target: format_metric_title(
            template.display_name,
            target
        ),
        explanation_formatter=lambda point_value, target: (
            (
                f"Generated {point_value}-point WOM metric target "
                f"from the {template.display_name} template."
            ),
        ),
        include_generation_note=False,
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
        activity_group_id="skilling_minigames",
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
        activity_group_id="skilling_minigames",
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
        activity_group_id="skilling_minigames",
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




DROP_GROUP_TILE_AUDIT_ALREADY_TEMPLATED = "already_static_template"
DROP_GROUP_TILE_AUDIT_ELIGIBLE_SINGLE_SOURCE = "eligible_single_source"
DROP_GROUP_TILE_AUDIT_REVIEW_CLUE_OR_ACTIVITY = "review_clue_or_activity"
DROP_GROUP_TILE_AUDIT_REVIEW_SET_SUBGROUP = "review_set_subgroup"
DROP_GROUP_TILE_AUDIT_REVIEW_MULTI_SOURCE = "review_multi_source"
DROP_GROUP_TILE_AUDIT_SKIPPED_NO_DROPS = "skipped_no_drops"


@dataclass(frozen=True)
class DropGroupTileAuditRow:
    drop_group_id: str
    display_name: str
    source_ids: tuple
    source_names: tuple
    drop_count: int
    classification: str
    reason: str
    supports_group_unique_tiles: bool = False
    supports_specific_drop_tiles: bool = False
    specific_drop_tile_count: int = 0


def get_static_drop_template_group_ids():
    return frozenset(
        template.drop_group_id
        for template in STATIC_DROP_TEMPLATES
    )


def get_drop_group_drop_count(group):
    return len(
        group.get("drop_ids")
        or ()
    )


def build_drop_id_source_id_map(drop_groups=DROP_GROUP_DATA):
    """Map drops to clear single-source ownership.

    Broad aggregate groups can repeat the same drop across multiple sources.
    Those groups are useful for group tiles, but should not disqualify a
    specific-drop tile when the item also has one clear single-source group.
    """

    drop_id_source_ids = {}

    for group in drop_groups:
        source_ids = tuple(
            group.get("source_ids")
            or ()
        )

        if len(source_ids) != 1:
            continue

        for drop_id in group.get("drop_ids") or ():
            drop_id_source_ids.setdefault(
                drop_id,
                set()
            ).add(source_ids[0])

    return {
        drop_id: frozenset(source_ids)
        for drop_id, source_ids in drop_id_source_ids.items()
    }


def count_specific_drop_tile_candidates(group, drop_id_source_ids):
    source_ids = tuple(
        group.get("source_ids")
        or ()
    )

    if len(source_ids) != 1:
        return 0

    source_id = source_ids[0]

    return sum(
        1
        for drop_id in group.get("drop_ids") or ()
        if drop_id_source_ids.get(drop_id) == frozenset((source_id,))
    )


def supports_group_unique_tile_generation(classification):
    return classification in {
        DROP_GROUP_TILE_AUDIT_ALREADY_TEMPLATED,
        DROP_GROUP_TILE_AUDIT_ELIGIBLE_SINGLE_SOURCE,
    }


def is_clue_or_activity_drop_group(group):
    searchable_text = " ".join(
        (
            group.get("drop_group_id")
            or "",
            group.get("display_name")
            or "",
            " ".join(
                group.get("source_ids")
                or ()
            ),
            " ".join(
                group.get("source_names")
                or ()
            ),
        )
    ).casefold()

    return any(
        marker in searchable_text
        for marker in (
            "clue",
            "aerial_fishing",
            "wintertodt",
            "tempoross",
            "guardians_of_the_rift",
            "soul_wars",
        )
    )


def is_set_subgroup_drop_group(group):
    group_id = (
        group.get("drop_group_id")
        or ""
    ).casefold()
    display_name = (
        group.get("display_name")
        or ""
    ).casefold()

    return (
        group_id.endswith("_set")
        or group_id.endswith("'s_set")
        or display_name.endswith(" set")
    )


def classify_drop_group_for_tile_audit(group, templated_group_ids=None):
    if templated_group_ids is None:
        templated_group_ids = get_static_drop_template_group_ids()

    drop_group_id = group.get("drop_group_id")

    if drop_group_id in templated_group_ids:
        return (
            DROP_GROUP_TILE_AUDIT_ALREADY_TEMPLATED,
            "Already emitted by STATIC_DROP_TEMPLATES.",
        )

    if get_drop_group_drop_count(group) == 0:
        return (
            DROP_GROUP_TILE_AUDIT_SKIPPED_NO_DROPS,
            "No drop IDs are available for tile generation.",
        )

    source_ids = tuple(
        group.get("source_ids")
        or ()
    )

    if len(source_ids) != 1:
        return (
            DROP_GROUP_TILE_AUDIT_REVIEW_MULTI_SOURCE,
            "Multiple sources need manual review before automatic tile generation.",
        )

    if is_clue_or_activity_drop_group(group):
        return (
            DROP_GROUP_TILE_AUDIT_REVIEW_CLUE_OR_ACTIVITY,
            "Clue or activity-style groups need manual review for suitable targets.",
        )

    if is_set_subgroup_drop_group(group):
        return (
            DROP_GROUP_TILE_AUDIT_REVIEW_SET_SUBGROUP,
            "Set subgroups need manual review to avoid overlapping broad groups.",
        )

    return (
        DROP_GROUP_TILE_AUDIT_ELIGIBLE_SINGLE_SOURCE,
        "Single-source drop group with drops; suitable for automatic tile review.",
    )


def build_drop_group_tile_audit_rows(drop_groups=None):
    if drop_groups is None:
        drop_groups = DROP_GROUP_DATA

    templated_group_ids = get_static_drop_template_group_ids()
    drop_id_source_ids = build_drop_id_source_id_map(drop_groups)

    rows = []

    for group in drop_groups:
        classification, reason = classify_drop_group_for_tile_audit(
            group,
            templated_group_ids=templated_group_ids,
        )
        specific_drop_tile_count = count_specific_drop_tile_candidates(
            group,
            drop_id_source_ids,
        )

        rows.append(
            DropGroupTileAuditRow(
                drop_group_id=group.get("drop_group_id"),
                display_name=group.get("display_name"),
                source_ids=tuple(
                    group.get("source_ids")
                    or ()
                ),
                source_names=tuple(
                    group.get("source_names")
                    or ()
                ),
                drop_count=get_drop_group_drop_count(group),
                classification=classification,
                reason=reason,
                supports_group_unique_tiles=supports_group_unique_tile_generation(
                    classification
                ),
                supports_specific_drop_tiles=specific_drop_tile_count > 0,
                specific_drop_tile_count=specific_drop_tile_count,
            )
        )

    return tuple(rows)


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
        drop_group_id="giant_mole_unique",
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
        drop_group_id="scurrius_unique",
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
        drop_group_id="sarachnis_unique",
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
        drop_group_id="barrows_brothers_unique",
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
        drop_group_id="kraken_unique",
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
        source_name="Wilderness",
        source_id="wilderness",
        boss_id=None,
        drop_group_id="wilderness_unique",
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
        source_name="Wilderness ring",
        source_id="wilderness_ring",
        boss_id=None,
        drop_group_id="wilderness_ring",
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
