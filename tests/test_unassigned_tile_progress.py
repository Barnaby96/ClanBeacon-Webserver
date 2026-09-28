import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils import database


@pytest.fixture(autouse=True)
def unassigned_tile_progress_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Unassigned tile progress tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


def create_team(team_name="Unassigned Guard Team"):
    database.add_team(
        team_name,
        0,
        None
    )

    return database.get_team_by_name(team_name)[3]


def create_player(
    player_name="Unassigned Guard Player",
    team_id=None
):
    if team_id is None:
        team_id = create_team()

    database.add_player(
        player_name,
        0,
        0,
        0,
        team_id,
        0
    )

    return database.get_player_by_name(player_name)[0]


def create_tile_with_condition(
    tile_name,
    condition_type,
    condition_trigger,
    target=1,
    board_coordinate=None,
    tile_points=5
):
    database.add_tile(
        tile_name,
        condition_type,
        condition_trigger,
        "",
        "FALSE",
        1,
        1,
        tile_points,
        ""
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tile_id
            FROM tiles
            WHERE tile_name = %s
            """,
            (tile_name,)
        )
        tile_id = int(cursor.fetchone()[0])

    if board_coordinate is None:
        database.set_tile_board_coordinate(
            tile_id,
            None
        )
    else:
        database.set_tile_board_coordinate(
            tile_id,
            board_coordinate
        )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tile_completion_paths (
                tile_id,
                completion_path,
                route_mode,
                route_target,
                require_unique
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                tile_id,
                1,
                "ALL",
                None,
                False
            )
        )

    condition_id = database.add_tile_condition(
        tile_id,
        1,
        condition_type,
        condition_trigger,
        target
    )

    return tile_id, condition_id


def assert_no_progress_or_completion(team_id, tile_id, condition_id):
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COALESCE(SUM(progress), 0)
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            """,
            (
                team_id,
                condition_id
            )
        )
        assert int(cursor.fetchone()[0]) == 0

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            """,
            (
                team_id,
                tile_id
            )
        )
        assert int(cursor.fetchone()[0]) == 0

        cursor.execute(
            """
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            """,
            (team_id,)
        )
        assert float(cursor.fetchone()[0]) == 0.0


def test_dink_event_progress_ignores_unassigned_tile():
    team_id = create_team()
    player_id = create_player(team_id=team_id)

    tile_id, condition_id = create_tile_with_condition(
        "Unassigned Dink Drop",
        "DROP",
        "Unassigned test drop"
    )

    results = database.apply_event_condition_progress(
        player_id,
        "DROP",
        "Unassigned test drop",
        1
    )

    assert results == []
    assert_no_progress_or_completion(
        team_id,
        tile_id,
        condition_id
    )


def test_wom_progress_ignores_unassigned_tile():
    team_id = create_team()
    player_id = create_player(team_id=team_id)

    tile_id, condition_id = create_tile_with_condition(
        "Unassigned WOM KC",
        "KILLCOUNT",
        "vorkath"
    )

    database.apply_wom_metric_progress(
        123456,
        player_id,
        "KILLCOUNT",
        "vorkath",
        1
    )

    assert_no_progress_or_completion(
        team_id,
        tile_id,
        condition_id
    )


def test_manual_submission_options_hide_unassigned_tiles():
    team_id = create_team()
    player_id = create_player(team_id=team_id)

    unassigned_tile_id, _ = create_tile_with_condition(
        "Unassigned Manual Option",
        "MANUAL",
        "manual option"
    )

    assigned_tile_id, condition_id = create_tile_with_condition(
        "Assigned Manual Option",
        "MANUAL",
        "manual option",
        board_coordinate="A1"
    )

    options = database.get_manual_evidence_submission_options(
        player_id
    )

    tile_ids = {
        option["tile_id"]
        for option in options["tiles"]
    }

    assert unassigned_tile_id not in tile_ids
    assert assigned_tile_id in tile_ids
    assert options["tiles"][0]["conditions"][0]["condition_id"] == condition_id


def test_manual_evidence_rejects_unassigned_tile_condition():
    team_id = create_team()
    player_id = create_player(team_id=team_id)

    tile_id, condition_id = create_tile_with_condition(
        "Unassigned Manual Submit",
        "MANUAL",
        "manual submit"
    )

    with pytest.raises(ValueError, match="not assigned"):
        database.add_manual_evidence(
            player_id=player_id,
            condition_id=condition_id,
            amount=1,
            evidence_path="manual/test.png",
            evidence_sha256="abc123",
            submission_source="WEB",
            submitter_id=123,
            submitter_name="Submitter"
        )

    assert_no_progress_or_completion(
        team_id,
        tile_id,
        condition_id
    )


def test_manual_review_rejects_pending_evidence_after_tile_unassigned():
    team_id = create_team()
    player_id = create_player(team_id=team_id)

    tile_id, condition_id = create_tile_with_condition(
        "Manual Review Initially Assigned",
        "MANUAL",
        "manual review",
        board_coordinate="B2"
    )

    evidence = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=1,
        evidence_path="manual/review.png",
        evidence_sha256="def456",
        submission_source="WEB",
        submitter_id=123,
        submitter_name="Submitter"
    )
    evidence_id = evidence["evidence_id"]

    database.set_tile_board_coordinate(
        tile_id,
        None
    )

    result = database.accept_pending_manual_evidence(
        evidence_id=evidence_id,
        review_source="WEB",
        reviewer_id=456,
        reviewer_name="Reviewer"
    )

    assert result["status"] == "TILE_UNASSIGNED"

    assert_no_progress_or_completion(
        team_id,
        tile_id,
        condition_id
    )


def test_low_level_progress_rejects_unassigned_tile_condition():
    team_id = create_team()

    tile_id, condition_id = create_tile_with_condition(
        "Unassigned Low Level Progress",
        "DROP",
        "low level drop"
    )

    with pytest.raises(ValueError, match="unassigned"):
        database.add_tile_condition_progress(
            team_id,
            condition_id,
            1
        )

    assert_no_progress_or_completion(
        team_id,
        tile_id,
        condition_id
    )


def test_assigned_tile_can_still_progress_and_award_points():
    team_id = create_team()
    player_id = create_player(team_id=team_id)

    tile_id, condition_id = create_tile_with_condition(
        "Assigned Dink Drop",
        "DROP",
        "Assigned test drop",
        board_coordinate="C3"
    )

    results = database.apply_event_condition_progress(
        player_id,
        "DROP",
        "Assigned test drop",
        1
    )

    assert len(results) == 1
    assert results[0]["completed"] is True

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            """,
            (
                team_id,
                tile_id
            )
        )
        assert int(cursor.fetchone()[0]) == 1

        cursor.execute(
            """
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            """,
            (team_id,)
        )
        assert float(cursor.fetchone()[0]) == 5.0

        cursor.execute(
            """
            SELECT progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            """,
            (
                team_id,
                condition_id
            )
        )
        assert int(cursor.fetchone()[0]) == 1
