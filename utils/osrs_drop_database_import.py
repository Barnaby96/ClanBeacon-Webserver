"""Normalise OSRS drop database spreadsheet rows.

This module deliberately accepts plain row dictionaries rather than reading
Excel directly. That keeps the parsing/test layer dependency-free and lets us
feed rows from Excel, CSV, admin upload or test fixtures later.
"""

from dataclasses import dataclass

from utils.board_generation import canonical_id


SOURCE_NAME_HEADER = "Source Name(s)"
SOURCE_ID_HEADER = "Source ID(s)"
GROUP_NAME_HEADER = "Group Name(s)"
GROUP_ID_HEADER = "Group ID(s)"
DROP_NAME_HEADER = "Drop Name"
DROP_ID_HEADER = "Drop ID"
DROP_RATE_HEADER = "Drop Rate(s)"
DROP_COUNTING_MODE_HEADER = "Drop Counting Mode"
DROP_QUANTITY_HEADER = "Drop Quantity"
INCLUDE_UNIQUE_HEADER = "Include In Unique Group?"
INCLUDE_PET_HEADER = "Include Pet?"
ACCESS_NOTES_HEADER = "Requirements / Access Notes"
NOTES_HEADER = "Notes"


@dataclass(frozen=True)
class ImportedDropRow:
    source_names: tuple[str, ...]
    source_ids: tuple[str, ...]
    group_names: tuple[str, ...]
    group_ids: tuple[str, ...]
    drop_name: str
    drop_id: str
    drop_rates: tuple[str, ...]
    drop_counting_mode: str
    drop_quantity: str
    include_in_unique_group: bool
    include_pet: bool
    access_notes: str
    notes: str


@dataclass(frozen=True)
class ImportedDropGroup:
    group_id: str
    group_name: str
    source_ids: tuple[str, ...]
    source_names: tuple[str, ...]
    drop_ids: tuple[str, ...]
    drop_names: tuple[str, ...]
    drop_rates: tuple[str, ...] = ()
    drop_counting_modes: tuple[str, ...] = ()
    drop_quantities: tuple[str, ...] = ()
    access_notes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    include_pet: bool = False

    @property
    def max_distinct_drop_count(self):
        return len(
            self.drop_ids
        )


@dataclass(frozen=True)
class ImportedDropDatabase:
    rows: tuple[ImportedDropRow, ...]
    groups: tuple[ImportedDropGroup, ...]

    @property
    def groups_by_id(self):
        return {
            group.group_id: group
            for group in self.groups
        }


def split_semicolon_values(value):
    if value is None:
        return ()

    text = str(
        value
    ).strip()

    if not text:
        return ()

    return tuple(
        part.strip()
        for part in text.split(";")
        if part.strip()
    )


def parse_yes_no(value, default=False):
    if value is None:
        return default

    text = str(
        value
    ).strip().lower()

    if not text:
        return default

    if text in {
        "yes",
        "y",
        "true",
        "1",
    }:
        return True

    if text in {
        "no",
        "n",
        "false",
        "0",
    }:
        return False

    raise ValueError(
        f"Expected yes/no value, got {value!r}"
    )



DROP_COUNTING_MODE_DISTINCT_DROPS = "distinct_drops"
DROP_COUNTING_MODE_ITEM_QUANTITY = "item_quantity"
DROP_COUNTING_MODE_DROP_EVENTS = "drop_events"

DROP_COUNTING_MODE_ALIASES = {
    "": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "distinct": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "distinct_drop": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "distinct_drops": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "unique": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "uniques": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "unique_n_of_set": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "n_of_set": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "set": DROP_COUNTING_MODE_DISTINCT_DROPS,
    "quantity": DROP_COUNTING_MODE_ITEM_QUANTITY,
    "item_quantity": DROP_COUNTING_MODE_ITEM_QUANTITY,
    "items": DROP_COUNTING_MODE_ITEM_QUANTITY,
    "drop": DROP_COUNTING_MODE_DROP_EVENTS,
    "drops": DROP_COUNTING_MODE_DROP_EVENTS,
    "drop_event": DROP_COUNTING_MODE_DROP_EVENTS,
    "drop_events": DROP_COUNTING_MODE_DROP_EVENTS,
    "roll": DROP_COUNTING_MODE_DROP_EVENTS,
    "rolls": DROP_COUNTING_MODE_DROP_EVENTS,
}


def parse_drop_counting_mode(value):
    normalised = "_".join(
        str(
            value or ""
        )
        .strip()
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .split()
    )

    if normalised not in DROP_COUNTING_MODE_ALIASES:
        raise ValueError(
            f"Unknown drop counting mode: {value}"
        )

    return DROP_COUNTING_MODE_ALIASES[
        normalised
    ]

def get_row_value(row, header):
    return row.get(
        header
    )


def build_ids_for_names(raw_ids, names, label):
    ids = split_semicolon_values(
        raw_ids
    )

    if not ids:
        return tuple(
            canonical_id(
                name
            )
            for name in names
        )

    if len(ids) != len(names):
        raise ValueError(
            f"{label} ID count must match {label} name count"
        )

    return tuple(
        canonical_id(
            value
        )
        for value in ids
    )


def normalise_drop_database_row(row):
    source_names = split_semicolon_values(
        get_row_value(
            row,
            SOURCE_NAME_HEADER,
        )
    )
    group_names = split_semicolon_values(
        get_row_value(
            row,
            GROUP_NAME_HEADER,
        )
    )

    drop_name = str(
        get_row_value(
            row,
            DROP_NAME_HEADER,
        )
        or ""
    ).strip()

    if not source_names:
        raise ValueError("Source Name(s) is required")

    if not group_names:
        raise ValueError("Group Name(s) is required")

    if not drop_name:
        raise ValueError("Drop Name is required")

    source_ids = build_ids_for_names(
        get_row_value(
            row,
            SOURCE_ID_HEADER,
        ),
        source_names,
        "Source",
    )
    group_ids = build_ids_for_names(
        get_row_value(
            row,
            GROUP_ID_HEADER,
        ),
        group_names,
        "Group",
    )

    raw_drop_id = get_row_value(
        row,
        DROP_ID_HEADER,
    )
    drop_id = canonical_id(
        raw_drop_id
        or drop_name
    )

    return ImportedDropRow(
        source_names=source_names,
        source_ids=source_ids,
        group_names=group_names,
        group_ids=group_ids,
        drop_name=drop_name,
        drop_id=drop_id,
        drop_rates=split_semicolon_values(
            get_row_value(
                row,
                DROP_RATE_HEADER,
            )
        ),
        drop_counting_mode=parse_drop_counting_mode(
            get_row_value(
                row,
                DROP_COUNTING_MODE_HEADER,
            )
        ),
        drop_quantity=str(
            get_row_value(
                row,
                DROP_QUANTITY_HEADER,
            )
            or ""
        ).strip(),
        include_in_unique_group=parse_yes_no(
            get_row_value(
                row,
                INCLUDE_UNIQUE_HEADER,
            ),
            default=False,
        ),
        include_pet=parse_yes_no(
            get_row_value(
                row,
                INCLUDE_PET_HEADER,
            ),
            default=False,
        ),
        access_notes=str(
            get_row_value(
                row,
                ACCESS_NOTES_HEADER,
            )
            or ""
        ).strip(),
        notes=str(
            get_row_value(
                row,
                NOTES_HEADER,
            )
            or ""
        ).strip(),
    )


def append_unique(values, value):
    if value in values:
        return

    values.append(
        value
    )


def build_imported_drop_groups(rows):
    group_data_by_id = {}

    for row in rows:
        if not row.include_in_unique_group:
            continue

        for index, group_id in enumerate(
            row.group_ids
        ):
            group_name = row.group_names[
                index
            ]

            group_data = group_data_by_id.setdefault(
                group_id,
                {
                    "group_name": group_name,
                    "source_ids": [],
                    "source_names": [],
                    "drop_ids": [],
                    "drop_names": [],
                    "drop_rates": [],
                    "drop_counting_modes": [],
                    "drop_quantities": [],
                    "access_notes": [],
                    "notes": [],
                    "include_pet": False,
                },
            )

            for source_id, source_name in zip(
                row.source_ids,
                row.source_names,
            ):
                append_unique(
                    group_data["source_ids"],
                    source_id,
                )
                append_unique(
                    group_data["source_names"],
                    source_name,
                )

            if row.drop_id not in group_data["drop_ids"]:
                group_data["drop_ids"].append(
                    row.drop_id
                )
                group_data["drop_names"].append(
                    row.drop_name
                )
                group_data["drop_rates"].append(
                    "; ".join(
                        row.drop_rates
                    )
                )
                group_data["drop_counting_modes"].append(
                    row.drop_counting_mode
                )
                group_data["drop_quantities"].append(
                    row.drop_quantity
                )

            append_unique(
                group_data["access_notes"],
                row.access_notes,
            )
            append_unique(
                group_data["notes"],
                row.notes,
            )

            group_data["include_pet"] = (
                group_data["include_pet"]
                or row.include_pet
            )

    return tuple(
        ImportedDropGroup(
            group_id=group_id,
            group_name=group_data["group_name"],
            source_ids=tuple(
                group_data["source_ids"]
            ),
            source_names=tuple(
                group_data["source_names"]
            ),
            drop_ids=tuple(
                group_data["drop_ids"]
            ),
            drop_names=tuple(
                group_data["drop_names"]
            ),
            drop_rates=tuple(
                group_data["drop_rates"]
            ),
            drop_counting_modes=tuple(
                group_data["drop_counting_modes"]
            ),
            drop_quantities=tuple(
                group_data["drop_quantities"]
            ),
            access_notes=tuple(
                value
                for value in group_data["access_notes"]
                if value
            ),
            notes=tuple(
                value
                for value in group_data["notes"]
                if value
            ),
            include_pet=group_data["include_pet"],
        )
        for group_id, group_data in sorted(
            group_data_by_id.items()
        )
    )

def normalise_drop_database_rows(raw_rows):
    rows = tuple(
        normalise_drop_database_row(
            raw_row
        )
        for raw_row in raw_rows
    )

    return ImportedDropDatabase(
        rows=rows,
        groups=build_imported_drop_groups(
            rows
        ),
    )
