"""Atomic OSRS Bingo tile components.

A component is one reusable, valid thing ClanBeacon can track or use when
generating a tile. It is not necessarily a complete tile by itself.
"""

from dataclasses import dataclass, field
from enum import Enum

from utils.board_generation import (
    AccessProfile,
    TileCategory,
    TrackingSource,
    build_tag,
    canonical_id,
)


class TileComponentType(str, Enum):
    KILLCOUNT = "KILLCOUNT"
    DROP = "DROP"
    PET = "PET"
    EXPERIENCE = "EXPERIENCE"
    WOM_METRIC = "WOM_METRIC"
    MANUAL = "MANUAL"


DEFAULT_CATEGORY_BY_COMPONENT_TYPE = {
    TileComponentType.KILLCOUNT: TileCategory.KILLCOUNT,
    TileComponentType.DROP: TileCategory.DROP,
    TileComponentType.PET: TileCategory.PET,
    TileComponentType.EXPERIENCE: TileCategory.SKILL,
    TileComponentType.WOM_METRIC: TileCategory.HYBRID,
    TileComponentType.MANUAL: TileCategory.HYBRID,
}


def normalise_component_groups(groups):
    normalised_groups = tuple(
        canonical_id(group)
        for group in groups
    )

    if any(
        group is None or group == ""
        for group in normalised_groups
    ):
        raise ValueError("Component groups cannot be empty.")

    if len(set(normalised_groups)) != len(normalised_groups):
        raise ValueError("Component groups must be unique.")

    return normalised_groups


def normalise_component_recipe_ids(recipe_ids):
    normalised_recipe_ids = tuple(
        canonical_id(recipe_id).upper()
        for recipe_id in recipe_ids
    )

    if not normalised_recipe_ids:
        raise ValueError("Components must support at least one recipe.")

    if any(
        recipe_id is None or recipe_id == ""
        for recipe_id in normalised_recipe_ids
    ):
        raise ValueError("Component recipe ids cannot be empty.")

    if len(set(normalised_recipe_ids)) != len(normalised_recipe_ids):
        raise ValueError("Component recipe ids must be unique.")

    return normalised_recipe_ids


@dataclass(frozen=True)
class TileComponent:
    component_id: str
    component_type: TileComponentType
    display_name: str
    tracking_source: TrackingSource
    target_model_id: str
    primary_category: TileCategory | None = None
    metric_id: str | None = None
    source_id: str | None = None
    skill_id: str | None = None
    boss_id: str | None = None
    drop_id: str | None = None
    drop_group_id: str | None = None
    pet_id: str | None = None
    groups: tuple[str, ...] = ()
    compatible_recipe_ids: tuple[str, ...] = ("SINGLE",)
    access_profile: AccessProfile = field(default_factory=AccessProfile)
    rng_level: int = 0
    effort_profile_id: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        component_type = TileComponentType(
            self.component_type
        )
        tracking_source = TrackingSource(
            self.tracking_source
        )

        component_id = canonical_id(
            self.component_id
        )
        target_model_id = canonical_id(
            self.target_model_id
        )

        if component_id is None or component_id == "":
            raise ValueError("Components require a component_id.")

        if not self.display_name:
            raise ValueError("Components require a display_name.")

        if target_model_id is None or target_model_id == "":
            raise ValueError("Components require a target_model_id.")

        if self.rng_level < 0:
            raise ValueError("Component rng_level cannot be negative.")

        object.__setattr__(
            self,
            "component_type",
            component_type,
        )
        object.__setattr__(
            self,
            "tracking_source",
            tracking_source,
        )
        object.__setattr__(
            self,
            "component_id",
            component_id,
        )
        object.__setattr__(
            self,
            "target_model_id",
            target_model_id,
        )
        object.__setattr__(
            self,
            "primary_category",
            self.primary_category or DEFAULT_CATEGORY_BY_COMPONENT_TYPE[
                component_type
            ],
        )

        for field_name in (
            "metric_id",
            "source_id",
            "skill_id",
            "boss_id",
            "drop_id",
            "drop_group_id",
            "pet_id",
            "effort_profile_id",
        ):
            object.__setattr__(
                self,
                field_name,
                canonical_id(
                    getattr(
                        self,
                        field_name,
                    )
                ),
            )

        object.__setattr__(
            self,
            "groups",
            normalise_component_groups(
                self.groups
            ),
        )
        object.__setattr__(
            self,
            "compatible_recipe_ids",
            normalise_component_recipe_ids(
                self.compatible_recipe_ids
            ),
        )
        object.__setattr__(
            self,
            "notes",
            tuple(
                self.notes
            ),
        )

    def supports_recipe(self, recipe_id):
        return canonical_id(
            recipe_id
        ).upper() in self.compatible_recipe_ids

    @property
    def hard_unique_tags(self):
        tag_values = (
            ("component", self.component_id),
            ("metric", self.metric_id),
            ("source", self.source_id),
            ("skill", self.skill_id),
            ("boss", self.boss_id),
            ("drop", self.drop_id),
            ("drop_group", self.drop_group_id),
            ("pet", self.pet_id),
            ("effort_profile", self.effort_profile_id),
        )

        tags = {
            build_tag(
                tag_type,
                value,
            )
            for tag_type, value in tag_values
            if value
        }

        tags.update(
            build_tag(
                "activity_group",
                group,
            )
            for group in self.groups
        )

        return frozenset(tags)
