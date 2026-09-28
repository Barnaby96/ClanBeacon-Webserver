import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils import database


_ORIGINAL_RESET_TABLES = database.reset_tables
_ORIGINAL_ADD_TILE_WITH_CONDITIONS = database.add_tile_with_conditions
_ORIGINAL_ADD_TILE = database.add_tile


_DO_NOT_AUTO_ASSIGN_NEW_TILE_TESTS = {
    "test_board.py::test_set_tile_board_coordinate_assigns_empty_coordinate",
    "test_board.py::test_set_tile_board_coordinate_displaces_to_unassigned",
    "test_board.py::test_legacy_tile_creation_rejects_twenty_sixth_tile",
    "test_board.py::test_modern_tile_creation_rejects_twenty_sixth_tile",
    "test_board.py::test_update_tile_board_position_json_rejects_invalid_coordinate",
}


def should_auto_assign_test_tiles():
    current_test = os.environ.get(
        "PYTEST_CURRENT_TEST",
        ""
    ).replace(
        "\\",
        "/"
    )

    current_nodeid = current_test.split(" ")[0]

    return not any(
        current_nodeid.endswith(test_name)
        for test_name in _DO_NOT_AUTO_ASSIGN_NEW_TILE_TESTS
    )


def assign_tile_to_first_free_coordinate(tile_id):
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT board_coordinate
            FROM tiles
            WHERE tile_id = %s
            """,
            (tile_id,)
        )
        existing_coordinate = cursor.fetchone()

        if existing_coordinate is not None and existing_coordinate[0] is not None:
            return existing_coordinate[0]

        cursor.execute(
            """
            SELECT board_coordinate
            FROM tiles
            WHERE board_coordinate IS NOT NULL
            """
        )
        used_coordinates = {
            row[0]
            for row in cursor.fetchall()
        }

    for row in "ABCDE":
        for column in range(1, 6):
            coordinate = f"{row}{column}"

            if coordinate not in used_coordinates:
                database.set_tile_board_coordinate(
                    tile_id,
                    coordinate
                )
                return coordinate

    raise AssertionError(
        "No free board coordinate available for test tile."
    )


def assign_existing_tiles_to_board():
    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tile_id
            FROM tiles
            WHERE board_coordinate IS NULL
            ORDER BY tile_id
            LIMIT 25
            """
        )
        tile_ids = [
            row[0]
            for row in cursor.fetchall()
        ]

    for tile_id in tile_ids:
        assign_tile_to_first_free_coordinate(tile_id)


def reset_tables_with_board_assignments(*args, **kwargs):
    result = _ORIGINAL_RESET_TABLES(*args, **kwargs)

    if should_auto_assign_test_tiles():
        assign_existing_tiles_to_board()

    return result


def add_tile_with_board_assignment(*args, **kwargs):
    tile_id = _ORIGINAL_ADD_TILE(*args, **kwargs)

    if should_auto_assign_test_tiles():
        assign_tile_to_first_free_coordinate(tile_id)

    return tile_id


def add_tile_with_conditions_with_board_assignment(*args, **kwargs):
    tile_id = _ORIGINAL_ADD_TILE_WITH_CONDITIONS(*args, **kwargs)

    if should_auto_assign_test_tiles():
        assign_tile_to_first_free_coordinate(tile_id)

    return tile_id


database.reset_tables = reset_tables_with_board_assignments
database.add_tile_with_conditions = add_tile_with_conditions_with_board_assignment
database.add_tile = add_tile_with_board_assignment
