from dataclasses import dataclass
from decimal import Decimal


DEFAULT_SOURCE_ACCESS_REQUIREMENT_MULTIPLIER = Decimal("1")
DEFAULT_SOURCE_DIFFICULTY_MULTIPLIER = Decimal("1")


@dataclass(frozen=True)
class DropTileSourceEffortProfile:
    source_id: str
    access_requirement_multiplier: Decimal = DEFAULT_SOURCE_ACCESS_REQUIREMENT_MULTIPLIER
    source_difficulty_multiplier: Decimal = DEFAULT_SOURCE_DIFFICULTY_MULTIPLIER
    reason: str = ""


CURATED_DROP_TILE_SOURCE_EFFORT_PROFILES = {
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
