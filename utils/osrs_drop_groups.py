"""Drop group definitions for generated OSRS Bingo drop tiles."""

from dataclasses import dataclass

from utils.board_generation import canonical_id
from utils.osrs_drop_group_data import DROP_GROUP_DATA


@dataclass(frozen=True)
class DropGroupDefinition:
    drop_group_id: str
    display_name: str
    source_ids: tuple[str, ...]
    drop_ids: tuple[str, ...]
    source_names: tuple[str, ...] = ()
    drop_names: tuple[str, ...] = ()
    include_pet: bool = False
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        drop_group_id = canonical_id(
            self.drop_group_id
        )
        source_ids = tuple(
            canonical_id(
                source_id
            )
            for source_id in self.source_ids
        )
        drop_ids = tuple(
            canonical_id(
                drop_id
            )
            for drop_id in self.drop_ids
        )
        source_names = tuple(
            source_name.strip()
            for source_name in self.source_names
            if source_name.strip()
        )
        drop_names = tuple(
            drop_name.strip()
            for drop_name in self.drop_names
            if drop_name.strip()
        )

        if not drop_group_id:
            raise ValueError("drop_group_id is required")

        if not source_ids:
            raise ValueError("source_ids must contain at least one source")

        if not drop_ids:
            raise ValueError("drop_ids must contain at least one drop")

        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source_ids must be unique within a drop group")

        if len(set(drop_ids)) != len(drop_ids):
            raise ValueError("drop_ids must be unique within a drop group")

        if drop_names and len(drop_names) != len(drop_ids):
            raise ValueError("drop_names must match drop_ids")

        object.__setattr__(
            self,
            "drop_group_id",
            drop_group_id,
        )
        object.__setattr__(
            self,
            "source_ids",
            source_ids,
        )
        object.__setattr__(
            self,
            "drop_ids",
            drop_ids,
        )
        object.__setattr__(
            self,
            "source_names",
            source_names,
        )
        object.__setattr__(
            self,
            "drop_names",
            drop_names,
        )

    @classmethod
    def from_data_record(cls, record):
        return cls(
            drop_group_id=record["drop_group_id"],
            display_name=record["display_name"],
            source_ids=tuple(
                record["source_ids"]
            ),
            source_names=tuple(
                record.get(
                    "source_names",
                    (),
                )
            ),
            drop_ids=tuple(
                record["drop_ids"]
            ),
            drop_names=tuple(
                record.get(
                    "drop_names",
                    (),
                )
            ),
            include_pet=bool(
                record.get(
                    "include_pet",
                    False,
                )
            ),
        )

    @property
    def source_id(self):
        if len(
            self.source_ids
        ) != 1:
            return None

        return self.source_ids[0]

    @property
    def max_distinct_drop_count(self):
        return len(
            self.drop_ids
        )


DROP_GROUP_DEFINITIONS = tuple(
    DropGroupDefinition.from_data_record(
        record
    )
    for record in DROP_GROUP_DATA
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
