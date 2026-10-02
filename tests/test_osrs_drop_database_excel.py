from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest

from utils.osrs_drop_database_excel import (
    format_drop_database_summary,
    load_drop_database_xlsx,
    read_xlsx_rows,
    summarise_imported_drop_database,
)


def column_letters(index):
    index += 1
    letters = ""

    while index:
        index, remainder = divmod(
            index - 1,
            26,
        )
        letters = chr(
            65 + remainder
        ) + letters

    return letters


def worksheet_xml(rows, use_shared_strings=False):
    shared_string_index_by_value = {}
    shared_strings = []

    xml_rows = []

    for row_number, row in enumerate(
        rows,
        start=1,
    ):
        cell_xml = []

        for column_index, value in enumerate(
            row,
        ):
            if value in (None, ""):
                continue

            reference = f"{column_letters(column_index)}{row_number}"
            text = str(
                value
            )

            if use_shared_strings:
                if text not in shared_string_index_by_value:
                    shared_string_index_by_value[
                        text
                    ] = len(
                        shared_strings
                    )
                    shared_strings.append(
                        text
                    )

                cell_xml.append(
                    f'<c r="{reference}" t="s"><v>'
                    f'{shared_string_index_by_value[text]}'
                    f'</v></c>'
                )
            else:
                cell_xml.append(
                    f'<c r="{reference}" t="inlineStr"><is><t>'
                    f'{escape(text)}'
                    f'</t></is></c>'
                )

        xml_rows.append(
            f'<row r="{row_number}">{"".join(cell_xml)}</row>'
        )

    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        f'{"".join(xml_rows)}'
        '</sheetData>'
        '</worksheet>'
    )

    shared_strings_xml = None

    if use_shared_strings:
        shared_strings_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + "".join(
                f"<si><t>{escape(value)}</t></si>"
                for value in shared_strings
            )
            + "</sst>"
        )

    return worksheet, shared_strings_xml


def write_workbook(path, rows, sheet_name="Drops", use_shared_strings=False):
    worksheet, shared_strings = worksheet_xml(
        rows,
        use_shared_strings=use_shared_strings,
    )

    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        f'<sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>'
        '</sheets>'
        '</workbook>'
    )

    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    with ZipFile(
        path,
        "w",
    ) as archive:
        archive.writestr(
            "xl/workbook.xml",
            workbook,
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            relationships,
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            worksheet,
        )

        if shared_strings is not None:
            archive.writestr(
                "xl/sharedStrings.xml",
                shared_strings,
            )


def test_read_xlsx_rows_accepts_singular_headers_and_inline_strings(tmp_path):
    workbook_path = tmp_path / "drops.xlsx"

    write_workbook(
        workbook_path,
        (
            (
                "Source Name",
                "Group Name",
                "Drop Name",
                "Drop Rate",
                "Include In Unique Group?",
            ),
            (
                "Dagannoth Rex",
                "Dagannoth Rex uniques",
                "Berserker ring",
                "1/128",
                "Yes",
            ),
        ),
    )

    rows = read_xlsx_rows(
        workbook_path
    )

    assert rows == (
        {
            "Source Name(s)": "Dagannoth Rex",
            "Group Name(s)": "Dagannoth Rex uniques",
            "Drop Name": "Berserker ring",
            "Drop Rate(s)": "1/128",
            "Include In Unique Group?": "Yes",
        },
    )


def test_read_xlsx_rows_supports_shared_strings(tmp_path):
    workbook_path = tmp_path / "drops.xlsx"

    write_workbook(
        workbook_path,
        (
            (
                "Source Name(s)",
                "Group Name(s)",
                "Drop Name",
                "Include In Unique Group?",
            ),
            (
                "Zulrah",
                "Zulrah uniques",
                "Tanzanite fang",
                "Yes",
            ),
        ),
        use_shared_strings=True,
    )

    rows = read_xlsx_rows(
        workbook_path
    )

    assert rows[0]["Source Name(s)"] == "Zulrah"
    assert rows[0]["Drop Name"] == "Tanzanite fang"


def test_load_drop_database_xlsx_normalises_rows(tmp_path):
    workbook_path = tmp_path / "drops.xlsx"

    write_workbook(
        workbook_path,
        (
            (
                "Source Name",
                "Group Name",
                "Drop Name",
                "Include In Unique Group?",
            ),
            (
                "Dagannoth Rex",
                "Dagannoth Rex uniques",
                "Berserker ring",
                "Yes",
            ),
            (
                "Dagannoth Rex",
                "Dagannoth Rex uniques",
                "Warrior ring",
                "Yes",
            ),
            (
                "Dagannoth Rex",
                "Dagannoth Rex uniques",
                "Ring of wealth",
                "No",
            ),
        ),
    )

    database = load_drop_database_xlsx(
        workbook_path
    )

    assert len(
        database.rows
    ) == 3
    assert database.groups_by_id[
        "dagannoth_rex_uniques"
    ].drop_ids == (
        "berserker_ring",
        "warrior_ring",
    )


def test_summarise_imported_drop_database_counts_loaded_workbook(tmp_path):
    workbook_path = tmp_path / "drops.xlsx"

    write_workbook(
        workbook_path,
        (
            (
                "Source Name",
                "Group Name",
                "Drop Name",
                "Include In Unique Group?",
            ),
            (
                "Dagannoth Rex",
                "Dagannoth Rex uniques",
                "Berserker ring",
                "Yes",
            ),
            (
                "Dagannoth Rex",
                "Dagannoth Rex uniques",
                "Warrior ring",
                "Yes",
            ),
            (
                "Zulrah",
                "Zulrah uniques",
                "Tanzanite fang",
                "Yes",
            ),
            (
                "Zulrah",
                "Zulrah uniques",
                "Jar of swamp",
                "No",
            ),
        ),
    )

    database = load_drop_database_xlsx(
        workbook_path
    )
    summary = summarise_imported_drop_database(
        database
    )

    assert summary.row_count == 4
    assert summary.group_count == 2
    assert summary.source_count == 2
    assert summary.distinct_drop_count == 4
    assert summary.included_row_count == 3
    assert summary.excluded_row_count == 1
    assert summary.largest_groups[0] == (
        "dagannoth_rex_uniques",
        "Dagannoth Rex uniques",
        2,
    )

    formatted = format_drop_database_summary(
        summary
    )

    assert "Rows: 4" in formatted
    assert "Dagannoth Rex uniques (dagannoth_rex_uniques): 2" in formatted


def test_read_xlsx_rows_rejects_missing_worksheet(tmp_path):
    workbook_path = tmp_path / "drops.xlsx"

    write_workbook(
        workbook_path,
        (
            (
                "Source Name",
                "Group Name",
                "Drop Name",
            ),
        ),
        sheet_name="Drops",
    )

    with pytest.raises(
        ValueError,
        match="Worksheet 'Missing' not found",
    ):
        read_xlsx_rows(
            workbook_path,
            sheet_name="Missing",
        )
