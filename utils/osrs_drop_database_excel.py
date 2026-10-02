"""Read OSRS drop database Excel workbooks.

The parser is deliberately dependency-free. It reads the first worksheet, or a
named worksheet, from a simple .xlsx file and returns row dictionaries suitable
for the drop database import normaliser.
"""

from dataclasses import dataclass
from pathlib import Path
import sys
from xml.etree import ElementTree
from zipfile import ZipFile

from utils.osrs_drop_database_import import (
    ACCESS_NOTES_HEADER,
    DROP_ID_HEADER,
    DROP_NAME_HEADER,
    DROP_RATE_HEADER,
    GROUP_ID_HEADER,
    GROUP_NAME_HEADER,
    INCLUDE_PET_HEADER,
    INCLUDE_UNIQUE_HEADER,
    NOTES_HEADER,
    SOURCE_ID_HEADER,
    SOURCE_NAME_HEADER,
    normalise_drop_database_rows,
)


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NAMESPACES = {
    "main": MAIN_NS,
    "rel": REL_NS,
    "pkg_rel": PACKAGE_REL_NS,
}

CANONICAL_HEADER_BY_ALIAS = {
    "source name": SOURCE_NAME_HEADER,
    "source names": SOURCE_NAME_HEADER,
    "source name(s)": SOURCE_NAME_HEADER,
    "source id": SOURCE_ID_HEADER,
    "source ids": SOURCE_ID_HEADER,
    "source id(s)": SOURCE_ID_HEADER,
    "group name": GROUP_NAME_HEADER,
    "group names": GROUP_NAME_HEADER,
    "group name(s)": GROUP_NAME_HEADER,
    "group id": GROUP_ID_HEADER,
    "group ids": GROUP_ID_HEADER,
    "group id(s)": GROUP_ID_HEADER,
    "drop name": DROP_NAME_HEADER,
    "drop id": DROP_ID_HEADER,
    "drop rate": DROP_RATE_HEADER,
    "drop rates": DROP_RATE_HEADER,
    "drop rate(s)": DROP_RATE_HEADER,
    "include in unique group?": INCLUDE_UNIQUE_HEADER,
    "include in unique group": INCLUDE_UNIQUE_HEADER,
    "include pet?": INCLUDE_PET_HEADER,
    "include pet": INCLUDE_PET_HEADER,
    "requirements / access notes": ACCESS_NOTES_HEADER,
    "requirements/access notes": ACCESS_NOTES_HEADER,
    "access notes": ACCESS_NOTES_HEADER,
    "requirements": ACCESS_NOTES_HEADER,
    "notes": NOTES_HEADER,
}


@dataclass(frozen=True)
class DropDatabaseImportSummary:
    row_count: int
    group_count: int
    source_count: int
    distinct_drop_count: int
    included_row_count: int
    excluded_row_count: int
    largest_groups: tuple[tuple[str, str, int], ...]


def canonicalise_header(header):
    text = str(
        header or ""
    ).strip()

    return CANONICAL_HEADER_BY_ALIAS.get(
        text.lower(),
        text,
    )


def load_shared_strings(archive):
    try:
        data = archive.read(
            "xl/sharedStrings.xml"
        )
    except KeyError:
        return ()

    root = ElementTree.fromstring(
        data
    )

    values = []

    for string_item in root.findall(
        "main:si",
        NAMESPACES,
    ):
        values.append(
            "".join(
                text_node.text or ""
                for text_node in string_item.findall(
                    ".//main:t",
                    NAMESPACES,
                )
            )
        )

    return tuple(
        values
    )


def get_sheet_paths_by_name(archive):
    workbook_root = ElementTree.fromstring(
        archive.read(
            "xl/workbook.xml"
        )
    )
    rels_root = ElementTree.fromstring(
        archive.read(
            "xl/_rels/workbook.xml.rels"
        )
    )

    rel_target_by_id = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in rels_root.findall(
            "pkg_rel:Relationship",
            NAMESPACES,
        )
    }

    sheet_paths_by_name = {}

    for sheet in workbook_root.findall(
        "main:sheets/main:sheet",
        NAMESPACES,
    ):
        sheet_name = sheet.attrib["name"]
        relationship_id = sheet.attrib[
            f"{{{REL_NS}}}id"
        ]
        target = rel_target_by_id[
            relationship_id
        ]

        if target.startswith(
            "/"
        ):
            sheet_path = target.lstrip(
                "/"
            )
        else:
            sheet_path = "xl/" + target

        sheet_paths_by_name[
            sheet_name
        ] = sheet_path

    return sheet_paths_by_name


def column_index_from_cell_reference(cell_reference):
    letters = "".join(
        character
        for character in cell_reference
        if character.isalpha()
    )

    index = 0

    for character in letters:
        index = index * 26 + (
            ord(
                character.upper()
            )
            - ord(
                "A"
            )
            + 1
        )

    return index - 1


def read_cell_value(cell, shared_strings):
    cell_type = cell.attrib.get(
        "t"
    )

    if cell_type == "inlineStr":
        return "".join(
            text_node.text or ""
            for text_node in cell.findall(
                ".//main:t",
                NAMESPACES,
            )
        )

    value_node = cell.find(
        "main:v",
        NAMESPACES,
    )

    if value_node is None:
        return ""

    raw_value = value_node.text or ""

    if cell_type == "s":
        return shared_strings[
            int(
                raw_value
            )
        ]

    if cell_type == "b":
        return (
            "TRUE"
            if raw_value == "1"
            else "FALSE"
        )

    return raw_value


def read_worksheet_values(archive, worksheet_path, shared_strings):
    worksheet_root = ElementTree.fromstring(
        archive.read(
            worksheet_path
        )
    )

    rows = []

    for row in worksheet_root.findall(
        "main:sheetData/main:row",
        NAMESPACES,
    ):
        values = []

        for cell in row.findall(
            "main:c",
            NAMESPACES,
        ):
            cell_reference = cell.attrib.get(
                "r",
                ""
            )
            column_index = (
                column_index_from_cell_reference(
                    cell_reference
                )
                if cell_reference
                else len(
                    values
                )
            )

            while len(
                values
            ) <= column_index:
                values.append(
                    ""
                )

            values[
                column_index
            ] = read_cell_value(
                cell,
                shared_strings,
            )

        rows.append(
            tuple(
                values
            )
        )

    return tuple(
        rows
    )


def read_xlsx_rows(path, sheet_name=None):
    path = Path(
        path
    )

    with ZipFile(
        path
    ) as archive:
        sheet_paths_by_name = get_sheet_paths_by_name(
            archive
        )

        if sheet_name is None:
            worksheet_path = next(
                iter(
                    sheet_paths_by_name.values()
                )
            )
        else:
            try:
                worksheet_path = sheet_paths_by_name[
                    sheet_name
                ]
            except KeyError as exc:
                available_sheets = ", ".join(
                    sheet_paths_by_name
                )
                raise ValueError(
                    f"Worksheet {sheet_name!r} not found. "
                    f"Available sheets: {available_sheets}"
                ) from exc

        worksheet_values = read_worksheet_values(
            archive,
            worksheet_path,
            load_shared_strings(
                archive
            ),
        )

    if not worksheet_values:
        return ()

    headers = tuple(
        canonicalise_header(
            value
        )
        for value in worksheet_values[0]
    )

    rows = []

    for values in worksheet_values[1:]:
        if not any(
            str(
                value
            ).strip()
            for value in values
        ):
            continue

        row = {}

        for index, header in enumerate(
            headers
        ):
            if not header:
                continue

            row[
                header
            ] = (
                values[index]
                if index < len(
                    values
                )
                else ""
            )

        rows.append(
            row
        )

    return tuple(
        rows
    )


def load_drop_database_xlsx(path, sheet_name=None):
    return normalise_drop_database_rows(
        read_xlsx_rows(
            path,
            sheet_name=sheet_name,
        )
    )


def summarise_imported_drop_database(database, largest_group_limit=10):
    source_ids = set()
    drop_ids = set()
    included_row_count = 0
    excluded_row_count = 0

    for row in database.rows:
        source_ids.update(
            row.source_ids
        )
        drop_ids.add(
            row.drop_id
        )

        if row.include_in_unique_group:
            included_row_count += 1
        else:
            excluded_row_count += 1

    largest_groups = tuple(
        (
            group.group_id,
            group.group_name,
            group.max_distinct_drop_count,
        )
        for group in sorted(
            database.groups,
            key=lambda group: (
                -group.max_distinct_drop_count,
                group.group_id,
            ),
        )[:largest_group_limit]
    )

    return DropDatabaseImportSummary(
        row_count=len(
            database.rows
        ),
        group_count=len(
            database.groups
        ),
        source_count=len(
            source_ids
        ),
        distinct_drop_count=len(
            drop_ids
        ),
        included_row_count=included_row_count,
        excluded_row_count=excluded_row_count,
        largest_groups=largest_groups,
    )


def format_drop_database_summary(summary):
    lines = [
        f"Rows: {summary.row_count}",
        f"Groups: {summary.group_count}",
        f"Sources: {summary.source_count}",
        f"Distinct drops: {summary.distinct_drop_count}",
        f"Included rows: {summary.included_row_count}",
        f"Excluded rows: {summary.excluded_row_count}",
        "Largest groups:",
    ]

    for group_id, group_name, drop_count in summary.largest_groups:
        lines.append(
            f"- {group_name} ({group_id}): {drop_count}"
        )

    return "\n".join(
        lines
    )


def main(argv=None):
    argv = list(
        sys.argv[1:]
        if argv is None
        else argv
    )

    if not argv:
        raise SystemExit(
            "Usage: python -m utils.osrs_drop_database_excel "
            "<path-to-xlsx> [worksheet-name]"
        )

    database = load_drop_database_xlsx(
        argv[0],
        sheet_name=(
            argv[1]
            if len(
                argv
            )
            > 1
            else None
        ),
    )
    summary = summarise_imported_drop_database(
        database
    )

    print(
        format_drop_database_summary(
            summary
        )
    )


if __name__ == "__main__":
    main()
