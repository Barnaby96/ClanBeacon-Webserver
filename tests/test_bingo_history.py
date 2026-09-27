from datetime import datetime, timezone
from decimal import Decimal

from utils import database


def _create_history_record(title="Indoor Sky Bingo 2026-09-01 - 2026-09-07"):
    return database.create_bingo_history_record(
        title=title,
        clan_name="Indoor Sky",
        competition_id=123456,
        competition_starts_at=None,
        competition_ends_at=None,
        published_by_user_id=None,
        published_by_username="Organiser",
        final_message="Final results message",
        leaderboard_snapshot={
            "teams": [
                {
                    "team_id": 1,
                    "team_name": "Winning Team",
                    "rank": 1,
                    "bingo_points": 12.5,
                    "tiles_completed": 20,
                    "mvp_points": 8.5,
                    "mvp_players": [
                        {
                            "player_id": 10,
                            "player_name": "Team MVP"
                        }
                    ]
                }
            ],
            "clan": {
                "relevant_boss_kc": 123,
                "relevant_drop_quantity": 4,
                "relevant_xp": 5678
            }
        },
        board_snapshot={
            "tile_names_by_coordinate": {
                "A1": "First Tile"
            },
            "completed_coordinates": [
                "A1"
            ],
            "partial_coordinates": []
        }
    )


def test_bingo_history_record_survives_bingo_event_reset():
    database.reset_tables()

    history_id = _create_history_record()

    database.reset_bingo_event_data()

    record = database.get_bingo_history_record(history_id)

    assert record is not None
    assert record["title"] == "Indoor Sky Bingo 2026-09-01 - 2026-09-07"
    assert record["leaderboard_snapshot"]["teams"][0]["team_name"] == (
        "Winning Team"
    )
    assert record["board_snapshot"]["tile_names_by_coordinate"] == {
        "A1": "First Tile"
    }


def test_soft_deleted_bingo_history_record_is_hidden_by_default():
    database.reset_tables()

    history_id = _create_history_record("Indoor Sky Bingo Hidden")

    assert database.soft_delete_bingo_history_record(
        history_id,
        deleted_by_user_id=None,
        deleted_by_username="Organiser"
    ) is True

    assert database.get_bingo_history_record(history_id) is None

    deleted_record = database.get_bingo_history_record(
        history_id,
        include_deleted=True
    )

    assert deleted_record is not None
    assert deleted_record["deleted_at"] is not None
    assert deleted_record["deleted_by_username"] == "Organiser"


def test_soft_delete_returns_false_for_missing_history_record():
    database.reset_tables()

    assert database.soft_delete_bingo_history_record(
        999999,
        deleted_by_user_id=None,
        deleted_by_username="Organiser"
    ) is False


def test_bingo_history_snapshots_handle_database_value_types():
    database.reset_tables()

    history_id = database.create_bingo_history_record(
        title="Indoor Sky Bingo Decimal Test",
        clan_name="Indoor Sky",
        competition_id=123456,
        competition_starts_at=None,
        competition_ends_at=None,
        published_by_user_id=None,
        published_by_username="Organiser",
        final_message="Final results message",
        leaderboard_snapshot={
            "teams": [
                {
                    "team_id": 1,
                    "team_name": "Winning Team",
                    "rank": 1,
                    "bingo_points": Decimal("12.5"),
                    "published_marker": datetime(
                        2026,
                        9,
                        7,
                        tzinfo=timezone.utc
                    )
                }
            ],
            "clan": {}
        },
        board_snapshot={
            "tile_names_by_coordinate": {
                "A1": "First Tile"
            },
            "completed_coordinates": [
                "A1"
            ],
            "partial_coordinates": []
        }
    )

    record = database.get_bingo_history_record(history_id)

    assert record["leaderboard_snapshot"]["teams"][0]["bingo_points"] == 12.5
    assert record["leaderboard_snapshot"]["teams"][0]["published_marker"] == (
        "2026-09-07T00:00:00+00:00"
    )
