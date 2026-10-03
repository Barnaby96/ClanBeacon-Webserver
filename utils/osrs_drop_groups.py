"""Drop group definitions for generated OSRS Bingo drop tiles."""

from dataclasses import dataclass

from utils.board_generation import build_tag, canonical_id
from utils.osrs_drop_group_data import DROP_GROUP_DATA
from utils.osrs_drop_rate_metadata import parse_drop_rate


@dataclass(frozen=True)
class DropGroupDefinition:
    drop_group_id: str
    display_name: str
    source_ids: tuple[str, ...]
    drop_ids: tuple[str, ...]
    source_names: tuple[str, ...] = ()
    drop_names: tuple[str, ...] = ()
    drop_rates: tuple[str, ...] = ()
    drop_counting_modes: tuple[str, ...] = ()
    drop_quantities: tuple[str, ...] = ()
    access_notes: tuple[str, ...] = ()
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

        drop_rates = tuple(
            str(
                drop_rate
            ).strip()
            for drop_rate in self.drop_rates
        )
        drop_counting_modes = tuple(
            str(
                drop_counting_mode
            ).strip()
            for drop_counting_mode in self.drop_counting_modes
        )
        drop_quantities = tuple(
            str(
                drop_quantity
            ).strip()
            for drop_quantity in self.drop_quantities
        )
        access_notes = tuple(
            str(
                access_note
            ).strip()
            for access_note in self.access_notes
            if str(
                access_note
            ).strip()
        )
        notes = tuple(
            str(
                note
            ).strip()
            for note in self.notes
            if str(
                note
            ).strip()
        )

        if drop_names and len(drop_names) != len(drop_ids):
            raise ValueError("drop_names must match drop_ids")

        if drop_rates and len(drop_rates) != len(drop_ids):
            raise ValueError("drop_rates must match drop_ids")

        if drop_counting_modes and len(drop_counting_modes) != len(drop_ids):
            raise ValueError("drop_counting_modes must match drop_ids")

        if drop_quantities and len(drop_quantities) != len(drop_ids):
            raise ValueError("drop_quantities must match drop_ids")

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
        object.__setattr__(
            self,
            "drop_rates",
            drop_rates,
        )
        object.__setattr__(
            self,
            "drop_counting_modes",
            drop_counting_modes,
        )
        object.__setattr__(
            self,
            "drop_quantities",
            drop_quantities,
        )
        object.__setattr__(
            self,
            "access_notes",
            access_notes,
        )
        object.__setattr__(
            self,
            "notes",
            notes,
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
            drop_rates=tuple(
                record.get(
                    "drop_rates",
                    (),
                )
            ),
            drop_counting_modes=tuple(
                record.get(
                    "drop_counting_modes",
                    (),
                )
            ),
            drop_quantities=tuple(
                record.get(
                    "drop_quantities",
                    (),
                )
            ),
            access_notes=tuple(
                record.get(
                    "access_notes",
                    (),
                )
            ),
            notes=tuple(
                record.get(
                    "notes",
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
    def distinct_drop_indexes(self):
        if not self.drop_counting_modes:
            return tuple(
                range(
                    len(
                        self.drop_ids
                    )
                )
            )

        return tuple(
            index
            for index, drop_counting_mode in enumerate(
                self.drop_counting_modes
            )
            if drop_counting_mode in (
                "",
                "distinct_drops",
            )
        )

    @property
    def distinct_drop_ids(self):
        return tuple(
            self.drop_ids[
                index
            ]
            for index in self.distinct_drop_indexes
        )

    @property
    def distinct_drop_names(self):
        if not self.drop_names:
            return ()

        return tuple(
            self.drop_names[
                index
            ]
            for index in self.distinct_drop_indexes
        )

    @property
    def distinct_drop_rates(self):
        if not self.drop_rates:
            return ()

        return tuple(
            self.drop_rates[
                index
            ]
            for index in self.distinct_drop_indexes
        )

    @property
    def distinct_drop_rate_estimates(self):
        return tuple(
            parse_drop_rate(
                drop_rate
            )
            for drop_rate in self.distinct_drop_rates
            if drop_rate
        )

    @property
    def parseable_distinct_drop_rate_estimates(self):
        return tuple(
            estimate
            for estimate in self.distinct_drop_rate_estimates
            if estimate.parseable
        )

    @property
    def minimum_distinct_expected_rolls(self):
        estimates = self.parseable_distinct_drop_rate_estimates

        if not estimates:
            return None

        return min(
            estimate.minimum_expected_rolls
            for estimate in estimates
        )

    @property
    def maximum_distinct_expected_rolls(self):
        estimates = self.parseable_distinct_drop_rate_estimates

        if not estimates:
            return None

        return max(
            estimate.maximum_expected_rolls
            for estimate in estimates
        )

    @property
    def representative_distinct_expected_rolls(self):
        estimates = self.parseable_distinct_drop_rate_estimates

        if not estimates:
            return None

        return sum(
            estimate.representative_expected_rolls
            for estimate in estimates
        ) / len(
            estimates
        )

    @property
    def max_distinct_drop_count(self):
        return len(
            self.distinct_drop_ids
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


DROP_GROUP_OVERLAP_FAMILY_IDS_BY_GROUP_ID = {
    "wilderness_unique": (
        "wilderness_unique",
    ),
    "wilderness_ring": (
        "wilderness_unique",
    ),
}


def get_drop_group_overlap_family_ids(drop_group_id):
    return DROP_GROUP_OVERLAP_FAMILY_IDS_BY_GROUP_ID.get(
        canonical_id(
            drop_group_id
        ),
        (),
    )


def get_drop_group_overlap_hard_unique_tags(drop_group_id):
    return frozenset(
        build_tag(
            "drop_group_family",
            family_id,
        )
        for family_id in get_drop_group_overlap_family_ids(
            drop_group_id
        )
    )


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
