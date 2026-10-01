"""Drop group definitions for generated OSRS Bingo drop tiles."""

from dataclasses import dataclass

from utils.board_generation import canonical_id


@dataclass(frozen=True)
class DropGroupDefinition:
    drop_group_id: str
    display_name: str
    source_id: str
    drop_ids: tuple[str, ...]
    include_pet: bool = False
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        drop_group_id = canonical_id(self.drop_group_id)
        source_id = canonical_id(self.source_id)
        drop_ids = tuple(
            canonical_id(drop_id)
            for drop_id in self.drop_ids
        )

        if not drop_group_id:
            raise ValueError("drop_group_id is required")

        if not source_id:
            raise ValueError("source_id is required")

        if not drop_ids:
            raise ValueError("drop_ids must contain at least one drop")

        if len(set(drop_ids)) != len(drop_ids):
            raise ValueError("drop_ids must be unique within a drop group")

        object.__setattr__(
            self,
            "drop_group_id",
            drop_group_id,
        )
        object.__setattr__(
            self,
            "source_id",
            source_id,
        )
        object.__setattr__(
            self,
            "drop_ids",
            drop_ids,
        )

    @property
    def max_distinct_drop_count(self):
        return len(
            self.drop_ids
        )


DROP_GROUP_DEFINITIONS = (
    DropGroupDefinition(
        drop_group_id="dagannoth_rex_uniques",
        display_name="Dagannoth Rex uniques",
        source_id="dagannoth_rex",
        drop_ids=(
            "berserker_ring",
            "warrior_ring",
        ),
        include_pet=False,
        notes=(
            "Boss-specific relevant unique group.",
            "Pet and shared Dagannoth Kings drops should be modelled separately.",
        ),
    ),
)

DROP_GROUP_DEFINITIONS_BY_ID = {
    definition.drop_group_id: definition
    for definition in DROP_GROUP_DEFINITIONS
}


def get_drop_group_definition(drop_group_id):
    return DROP_GROUP_DEFINITIONS_BY_ID.get(
        canonical_id(
            drop_group_id
        )
    )


def get_max_distinct_drop_count(drop_group_id):
    definition = get_drop_group_definition(
        drop_group_id
    )

    if definition is None:
        return None

    return definition.max_distinct_drop_count


def filter_valid_drop_target_by_point_value(
    drop_group_id,
    target_by_point_value,
):
    max_distinct_drop_count = get_max_distinct_drop_count(
        drop_group_id
    )

    targets = dict(
        target_by_point_value
    )

    if max_distinct_drop_count is None:
        return targets

    return {
        point_value: target
        for point_value, target in targets.items()
        if target <= max_distinct_drop_count
    }
