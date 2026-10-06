from dataclasses import dataclass
from decimal import Decimal


DEFAULT_SOURCE_ACCESS_REQUIREMENT_MULTIPLIER = Decimal("1")
DEFAULT_SOURCE_DIFFICULTY_MULTIPLIER = Decimal("1")


@dataclass(frozen=True)
class DropTileSourceEffortProfile:
    source_id: str
    access_requirement_multiplier: Decimal = DEFAULT_SOURCE_ACCESS_REQUIREMENT_MULTIPLIER
    source_difficulty_multiplier: Decimal = DEFAULT_SOURCE_DIFFICULTY_MULTIPLIER
    minimum_point_value: int | None = None
    reason: str = ""


CURATED_DROP_TILE_SOURCE_EFFORT_PROFILES = {
    "zalcano": DropTileSourceEffortProfile(
        source_id="zalcano",
        access_requirement_multiplier=Decimal("1.5"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Zalcano uniques require Song of the Elves completion and Prifddinas access.",
    ),
    "wilderness_multi_source": DropTileSourceEffortProfile(
        source_id="wilderness_multi_source",
        access_requirement_multiplier=Decimal("1.5"),
        source_difficulty_multiplier=Decimal("2"),
        minimum_point_value=2,
        reason="Wilderness drop groups carry PvP risk, travel friction, and multi-source planning constraints.",
    ),
    "chaos_fanatic": DropTileSourceEffortProfile(
        source_id="chaos_fanatic",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Wilderness boss drops carry PvP risk and travel friction.",
    ),
    "crazy_archaeologist": DropTileSourceEffortProfile(
        source_id="crazy_archaeologist",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("1.25"),
        reason="Wilderness boss drops carry PvP risk and travel friction.",
    ),
    "scorpia": DropTileSourceEffortProfile(
        source_id="scorpia",
        access_requirement_multiplier=Decimal("1.5"),
        source_difficulty_multiplier=Decimal("1.75"),
        reason="Wilderness boss drops carry PvP risk and deeper Wilderness travel friction.",
    ),
    "superior_slayer_monster": DropTileSourceEffortProfile(
        source_id="superior_slayer_monster",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.5"),
        minimum_point_value=4,
        reason="Superior Slayer drops require Slayer access, task availability, and superior spawn RNG.",
    ),
    "corporeal_beast": DropTileSourceEffortProfile(
        source_id="corporeal_beast",
        access_requirement_multiplier=Decimal("1.5"),
        source_difficulty_multiplier=Decimal("4"),
        reason="Corporeal Beast uniques require high combat capability, slower kills, and are often group-content effort.",
    ),
    "dagannoth_prime": DropTileSourceEffortProfile(
        source_id="dagannoth_prime",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Dagannoth King uniques require Waterbirth access and multi-boss lair setup.",
    ),
    "dagannoth_rex": DropTileSourceEffortProfile(
        source_id="dagannoth_rex",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("1.25"),
        reason="Dagannoth King uniques require Waterbirth access and multi-boss lair setup.",
    ),
    "dagannoth_supreme": DropTileSourceEffortProfile(
        source_id="dagannoth_supreme",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Dagannoth King uniques require Waterbirth access and multi-boss lair setup.",
    ),
    "nex": DropTileSourceEffortProfile(
        source_id="nex",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("25"),
        reason="Nex uniques require high access, group-boss capability, and meaningful per-kill coordination.",
    ),
    "phantom_muspah": DropTileSourceEffortProfile(
        source_id="phantom_muspah",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Phantom Muspah uniques require quest access and stronger solo-boss capability.",
    ),
    "tormented_demon": DropTileSourceEffortProfile(
        source_id="tormented_demon",
        access_requirement_multiplier=Decimal("1.5"),
        source_difficulty_multiplier=Decimal("1.75"),
        reason="Tormented Demon drops require quest access and stronger combat capability.",
    ),
    "vorkath": DropTileSourceEffortProfile(
        source_id="vorkath",
        access_requirement_multiplier=Decimal("1.5"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Vorkath uniques require major quest access and reliable solo-boss capability.",
    ),
    "yama": DropTileSourceEffortProfile(
        source_id="yama",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("5"),
        reason="Yama drops require high-end boss capability and should not be treated as neutral-effort uniques.",
    ),
    "zulrah": DropTileSourceEffortProfile(
        source_id="zulrah",
        access_requirement_multiplier=Decimal("1.25"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Zulrah uniques require quest access and solo-boss capability.",
    ),
    "alchemical_hydra": DropTileSourceEffortProfile(
        source_id="alchemical_hydra",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Slayer boss drops require Slayer access, task availability, and boss-specific combat capability.",
    ),
    "araxxor": DropTileSourceEffortProfile(
        source_id="araxxor",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.75"),
        reason="Slayer boss drops require Slayer access, task availability, and boss-specific combat capability.",
    ),
    "cerberus": DropTileSourceEffortProfile(
        source_id="cerberus",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Slayer boss drops require Slayer access, task availability, and boss-specific combat capability.",
    ),
    "grotesque_guardians": DropTileSourceEffortProfile(
        source_id="grotesque_guardians",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.4"),
        reason="Slayer boss drops require Slayer access, task availability, and boss-specific combat capability.",
    ),
    "kraken": DropTileSourceEffortProfile(
        source_id="kraken",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.25"),
        reason="Slayer boss drops require Slayer access and task availability.",
    ),
    "thermonuclear_smoke_devil": DropTileSourceEffortProfile(
        source_id="thermonuclear_smoke_devil",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.25"),
        reason="Slayer boss drops require Slayer access and task availability.",
    ),
    "unsired": DropTileSourceEffortProfile(
        source_id="unsired",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("1.5"),
        reason="Unsired rolls come through Abyssal Sire, with high Slayer access and practical task constraints.",
    ),
    "chambers_of_xeric": DropTileSourceEffortProfile(
        source_id="chambers_of_xeric",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("50"),
        reason="Raid purple items need raid completion effort, team capability, and MVP/personal-point context.",
    ),
    "fortis_colosseum": DropTileSourceEffortProfile(
        source_id="fortis_colosseum",
        access_requirement_multiplier=Decimal("5"),
        source_difficulty_multiplier=Decimal("500"),
        reason="Fortis Colosseum completion rewards require Wave 12 completion and very high mechanical difficulty.",
    ),
    "theatre_of_blood": DropTileSourceEffortProfile(
        source_id="theatre_of_blood",
        access_requirement_multiplier=Decimal("2"),
        source_difficulty_multiplier=Decimal("60"),
        reason="Raid purple items need raid completion effort and high source difficulty.",
    ),
    "tombs_of_amascut": DropTileSourceEffortProfile(
        source_id="tombs_of_amascut",
        access_requirement_multiplier=Decimal("1.5"),
        source_difficulty_multiplier=Decimal("45"),
        reason="Raid purple items need raid completion effort and invocation/difficulty context.",
    ),
}


def get_drop_tile_source_effort_profile(source_id):
    return CURATED_DROP_TILE_SOURCE_EFFORT_PROFILES.get(
        source_id,
        DropTileSourceEffortProfile(
            source_id=source_id,
        ),
    )
