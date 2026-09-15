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
def wom_tracking_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "WOM tracking tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


def create_team(team_name):
    database.add_team(
        team_name,
        0,
        None
    )

    team = database.get_team_by_name(
        team_name
    )

    return team[3]


def create_player(player_name, team_id):
    database.add_player(
        player_name,
        0,
        0,
        0,
        team_id,
        0
    )

    player = database.get_player_by_name(
        player_name
    )

    return player[0]


def create_experience_tile(
    tile_name,
    metric,
    target
):
    tile_id = database.add_tile(
        tile_name,
        "EXPERIENCE",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        tile_name
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO tile_completion_paths (
                tile_id,
                completion_path,
                route_mode,
                route_target,
                require_unique
            )
            VALUES (%s, 1, 'ALL', NULL, FALSE)
            ''',
            (tile_id,)
        )

        cursor.execute(
            '''
            INSERT INTO tile_conditions (
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            )
            VALUES (%s, 1, 'EXPERIENCE', %s, %s)
            RETURNING condition_id
            ''',
            (
                tile_id,
                metric,
                target
            )
        )

        condition_id = cursor.fetchone()[0]

    return tile_id, condition_id


def get_condition_progress(
    team_id,
    condition_id
):
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COALESCE(progress, 0)
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                team_id,
                condition_id
            )
        )

        row = cursor.fetchone()

    if row is None:
        return 0

    return int(row[0])


def test_new_wom_condition_receives_competition_to_date_gain():
    team_id = create_team("Guthix")
    player_id = create_player(
        "MiningPlayer",
        team_id
    )

    competition_id = 12345

    _, existing_condition_id = (
        create_experience_tile(
            "Existing Mining Tile",
            "mining",
            1000
        )
    )

    first_result = database.apply_wom_metric_progress(
        competition_id,
        player_id,
        "EXPERIENCE",
        "mining",
        100
    )

    assert first_result["previous_gain"] == 0
    assert first_result["new_gain"] == 100

    assert get_condition_progress(
        team_id,
        existing_condition_id
    ) == 100

    _, new_condition_id = create_experience_tile(
        "New Mining Tile",
        "mining",
        1000
    )

    second_result = database.apply_wom_metric_progress(
        competition_id,
        player_id,
        "EXPERIENCE",
        "mining",
        150
    )

    assert second_result["previous_gain"] == 100
    assert second_result["new_gain"] == 50

    # The existing condition consumes only the 50 XP earned
    # since its previous WOM checkpoint.
    assert get_condition_progress(
        team_id,
        existing_condition_id
    ) == 150

    # A condition introduced during the competition counts from
    # the competition start, so it receives the full 150 XP.
    assert get_condition_progress(
        team_id,
        new_condition_id
    ) == 150

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT last_processed_gain
            FROM wom_metric_state
            WHERE competition_id = %s
              AND player_id = %s
              AND metric = 'mining'
            ''',
            (
                competition_id,
                player_id
            )
        )

        assert int(cursor.fetchone()[0]) == 150

        cursor.execute(
            '''
            SELECT
                condition_id,
                last_processed_gain
            FROM wom_condition_state
            WHERE competition_id = %s
              AND player_id = %s
            ORDER BY condition_id
            ''',
            (
                competition_id,
                player_id
            )
        )

        checkpoints = {
            int(condition_id): int(last_processed_gain)
            for condition_id, last_processed_gain
            in cursor.fetchall()
        }

    assert checkpoints == {
        existing_condition_id: 150,
        new_condition_id: 150
    }

    repeated_result = database.apply_wom_metric_progress(
        competition_id,
        player_id,
        "EXPERIENCE",
        "mining",
        150
    )

    assert repeated_result["previous_gain"] == 150
    assert repeated_result["new_gain"] == 0

    assert get_condition_progress(
        team_id,
        existing_condition_id
    ) == 150

    assert get_condition_progress(
        team_id,
        new_condition_id
    ) == 150


def test_schema_migration_seeds_existing_wom_condition_checkpoint():
    team_id = create_team("Saradomin")
    player_id = create_player(
        "ExistingMiningPlayer",
        team_id
    )

    competition_id = 67890

    _, condition_id = create_experience_tile(
        "Existing Mining Tile",
        "mining",
        1000
    )

    # Simulate a pre-upgrade database where this condition has
    # already received 100 XP and the old player/metric WOM
    # checkpoint has also advanced to 100.
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO tile_condition_progress (
                team_id,
                condition_id,
                progress
            )
            VALUES (%s, %s, 100)
            ''',
            (
                team_id,
                condition_id
            )
        )

        cursor.execute(
            '''
            INSERT INTO wom_metric_state (
                competition_id,
                player_id,
                metric,
                last_processed_gain
            )
            VALUES (%s, %s, 'mining', 100)
            ''',
            (
                competition_id,
                player_id
            )
        )

        cursor.execute(
            '''
            DROP TABLE wom_condition_state
            '''
        )

        conn.commit()

    database.ensure_schema()

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT last_processed_gain
            FROM wom_condition_state
            WHERE competition_id = %s
              AND player_id = %s
              AND condition_id = %s
            ''',
            (
                competition_id,
                player_id,
                condition_id
            )
        )

        migrated_checkpoint = cursor.fetchone()

    assert migrated_checkpoint is not None
    assert int(migrated_checkpoint[0]) == 100

    same_gain_result = database.apply_wom_metric_progress(
        competition_id,
        player_id,
        "EXPERIENCE",
        "mining",
        100
    )

    assert same_gain_result["previous_gain"] == 100
    assert same_gain_result["new_gain"] == 0

    # The migration must not replay the historical 100 XP.
    assert get_condition_progress(
        team_id,
        condition_id
    ) == 100

    later_result = database.apply_wom_metric_progress(
        competition_id,
        player_id,
        "EXPERIENCE",
        "mining",
        150
    )

    assert later_result["previous_gain"] == 100
    assert later_result["new_gain"] == 50

    # Only the genuinely new 50 XP is applied after migration.
    assert get_condition_progress(
        team_id,
        condition_id
    ) == 150


def test_process_wom_competition_notifies_completed_tile(
    monkeypatch
):
    from utils import (
        completion_notifications,
        wom_tracking
    )

    team_id = create_team(
        "WOM Notification Team"
    )

    create_player(
        "WOM Notification Player",
        team_id
    )

    player_row = database.get_player_by_name(
        "WOM Notification Player"
    )

    monkeypatch.setattr(
        database,
        "get_wom_competition_id",
        lambda: 12345
    )

    monkeypatch.setattr(
        database,
        "get_wom_tile_conditions",
        lambda: [
            (
                1,
                20,
                1,
                "EXPERIENCE",
                "mining",
                100
            )
        ]
    )

    monkeypatch.setattr(
        wom_tracking.wom,
        "get_competition_details",
        lambda competition_id, metric: {
            "participations": [
                {
                    "playerId": 999,
                    "progress": {
                        "gained": 100
                    }
                }
            ]
        }
    )

    monkeypatch.setattr(
        database,
        "get_player_by_wom_player_id",
        lambda wom_player_id: player_row
    )

    monkeypatch.setattr(
        database,
        "apply_wom_metric_progress",
        lambda *args, **kwargs: {
            "tiles": [
                {
                    "ready": True,
                    "tile_id": 20
                }
            ]
        }
    )

    monkeypatch.setattr(
        database,
        "complete_tile_with_contributions",
        lambda team_id, tile_id: True
    )

    notification_calls = []

    monkeypatch.setattr(
        completion_notifications,
        "notify_progress_completions",
        lambda progress_results: notification_calls.append(
            progress_results
        )
    )

    result = wom_tracking.process_wom_competition()

    assert result["tiles_completed"] == [
        {
            "tile_id": 20,
            "team_id": team_id,
            "metric": "mining"
        }
    ]

    assert notification_calls == [
        [
            {
                "team_id": team_id,
                "tile_id": 20,
                "completed": True
            }
        ]
    ]
