import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import create_app
from utils import database, manual_evidence_files


@pytest.fixture(autouse=True)
def player_data_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Player Data tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client

def create_dashboard_user(
    username,
    password,
    *,
    account_role="PLAYER",
    player_id=None
):
    database.add_user(
        username,
        password
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET
                account_role = %s,
                player_id = %s
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            ''',
            (
                account_role,
                player_id,
                username
            )
        )


def login_dashboard_user(
    client,
    username,
    password
):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

def create_team_and_player(
    team_name="Player Data Team",
    player_name="Player Data Player"
):
    database.add_team(
        team_name,
        0,
        None
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT team_id
            FROM teams
            WHERE LOWER(team_name) = LOWER(%s)
            ''',
            (team_name,)
        )
        team_id = cursor.fetchone()[0]

    database.add_player(
        player_name,
        0,
        0,
        0,
        team_id,
        0
    )

    player = database.get_player_by_name(player_name)

    return team_id, player[0]


def test_player_data_links_directly_to_team_board(client):
    _, player_id = create_team_and_player(
        team_name="BoardLinkTeam",
        player_name="BoardLinkPlayer"
    )

    create_dashboard_user(
        "Board Link Login",
        "test-password",
        player_id=player_id
    )

    login_response = login_dashboard_user(
        client,
        "Board Link Login",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/user/player/BoardLinkPlayer"
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert 'href="/board/BoardLinkTeam"' in html
    assert "View Board" in html


def test_player_bingo_evidence_displays_local_datetime(client, monkeypatch):
    from datetime import datetime, timezone

    player_name = "Local Timestamp Player"

    _, player_id = create_team_and_player(
        team_name="Local Timestamp Team",
        player_name=player_name
    )

    create_dashboard_user(
        "Local Timestamp Login",
        "test-password",
        player_id=player_id
    )

    login_response = login_dashboard_user(
        client,
        "Local Timestamp Login",
        "test-password"
    )

    assert login_response.status_code == 302

    monkeypatch.setattr(
        database,
        "get_player_bingo_evidence",
        lambda requested_player_id: [
            {
                "date": datetime(
                    2026, 9, 21, 18, 0,
                    tzinfo=timezone.utc
                ),
                "tile_name": "Local Timestamp Tile",
                "contribution": 1.0,
                "source": "Automatic submission",
                "evidence_type": "dink",
                "evidence_id": 12345,
                "screenshot_path": "test-screenshot.png",
                "status": "In progress"
            }
        ] if requested_player_id == player_id else []
    )

    monkeypatch.setattr(
        "routes.user_routes.resolve_dink_evidence_path",
        lambda **kwargs: "test-screenshot.png"
    )

    response = client.get(
        f"/user/player/{player_name}"
    )

    assert response.status_code == 200

    page = response.get_data(as_text=True)

    assert "Local Timestamp Tile" in page
    assert 'class="osrs-local-datetime"' in page
    assert 'datetime="2026-09-21T18:00:00+00:00"' in page


def create_test_tile(tile_name):
    return database.add_tile(
        tile_name,
        "KILLCOUNT",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        tile_name
    )


def add_killcount_condition(
    tile_id,
    metric,
    target=1,
    completion_path=1
):
    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO tile_conditions (
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            )
            VALUES (%s, %s, 'KILLCOUNT', %s, %s)
            ''',
            (
                tile_id,
                completion_path,
                metric,
                target
            )
        )


def set_wom_metric_gain(
    competition_id,
    player_id,
    metric,
    gain
):
    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO wom_metric_state (
                competition_id,
                player_id,
                metric,
                last_processed_gain
            )
            VALUES (%s, %s, %s, %s)
            ''',
            (
                competition_id,
                player_id,
                metric,
                gain
            )
        )


def test_relevant_drop_summary_aggregates_modern_drop_progress():
    team_id, player_id = create_team_and_player()

    tile_id = database.add_tile_with_conditions(
        tile_name="Relevant Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Burning claw",
                "target": 10
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "SUM",
                "route_target": 10
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )
        condition_id = cursor.fetchone()[0]

    event_id = database.add_dink_event(
        event_fingerprint="player-data-relevant-drop-dink",
        raw_payload={"type": "LOOT"},
        player_name="Player Data Player",
        player_id=player_id,
        event_type="LOOT"
    )

    database.process_dink_event_progress(
        event_id=event_id,
        player_id=player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Burning claw",
                "amount": 2
            }
        ]
    )

    submission = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=3,
        evidence_path="manual/relevant-drop-test.png",
        evidence_sha256="a" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    review_result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert review_result["status"] == "ACCEPTED"

    result = database.get_player_relevant_drop_summary(
        player_id
    )

    assert result == {
        "total_quantity": 5,
        "drops": [
            {
                "drop_name": "Burning claw",
                "quantity": 5
            }
        ]
    }


def test_relevant_drop_summary_ignores_invalidated_dink_progress():
    _, player_id = create_team_and_player()

    database.add_tile_with_conditions(
        tile_name="Invalidated Relevant Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Invalidated claw",
                "target": 10
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "SUM",
                "route_target": 10
            }
        ]
    )

    event_id = database.add_dink_event(
        event_fingerprint=(
            "player-data-invalidated-relevant-drop-dink"
        ),
        raw_payload={"type": "LOOT"},
        player_name="Player Data Player",
        player_id=player_id,
        event_type="LOOT"
    )

    database.process_dink_event_progress(
        event_id=event_id,
        player_id=player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Invalidated claw",
                "amount": 2
            }
        ]
    )

    before_invalidation = (
        database.get_player_relevant_drop_summary(
            player_id
        )
    )

    assert before_invalidation == {
        "total_quantity": 2,
        "drops": [
            {
                "drop_name": "Invalidated claw",
                "quantity": 2
            }
        ]
    }

    database.invalidate_bingo_evidence(
        subject_type="DINK_EVENT",
        subject_id=event_id,
        reason_code="INCORRECT_EVIDENCE",
        review_source="DISCORD",
        reviewer_id=987654321,
        reviewer_name="Invalidation Reviewer"
    )

    # Invalidation is deliberately separate from the original
    # Dink processing status, so reporting must explicitly exclude
    # invalidated evidence rather than relying on status changes.
    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT status
            FROM dink_events
            WHERE event_id = %s
            ''',
            (event_id,)
        )

        assert cursor.fetchone()[0] == "PROCESSED"

    after_invalidation = (
        database.get_player_relevant_drop_summary(
            player_id
        )
    )

    assert after_invalidation == {
        "total_quantity": 0,
        "drops": []
    }


def test_relevant_drop_summary_ignores_non_relevant_and_synthetic_rows():
    team_id, player_id = create_team_and_player()
    tile_id = create_test_tile("Relevant Drop Test")

    database.add_drop(
        team_id,
        player_id,
        "Player Data Player",
        "Unrelated drop",
        100,
        7,
        "Test source"
    )

    database.add_relevant_drop(
        team_id,
        player_id,
        tile_id,
        "Relevant Drop Test",
        "Synthetic counter",
        "Player Data Player",
        None
    )

    result = database.get_player_relevant_drop_summary(
        player_id
    )

    assert result == {
        "total_quantity": 0,
        "drops": []
    }


def test_relevant_boss_kc_counts_duplicate_metric_once():
    _, player_id = create_team_and_player()

    first_tile_id = create_test_tile(
        "Kill Brutus 5000 times"
    )
    second_tile_id = create_test_tile(
        "Kill Brutus or Bryophyta 500 times"
    )

    add_killcount_condition(
        first_tile_id,
        "brutus",
        5000
    )
    add_killcount_condition(
        second_tile_id,
        "brutus",
        500
    )
    add_killcount_condition(
        second_tile_id,
        "bryophyta",
        500,
        completion_path=2
    )

    competition_id = 12345
    database.set_wom_competition_id(competition_id)

    set_wom_metric_gain(
        competition_id,
        player_id,
        "brutus",
        108
    )
    set_wom_metric_gain(
        competition_id,
        player_id,
        "bryophyta",
        0
    )

    result = database.get_player_relevant_boss_kc_summary(
        player_id
    )

    assert result == {
        "total_kc": 108,
        "bosses": [
            {
                "metric": "brutus",
                "kc_gained": 108,
                "related_tiles": [
                    "Kill Brutus 5000 times",
                    "Kill Brutus or Bryophyta 500 times"
                ]
            }
        ]
    }


def test_relevant_boss_kc_without_competition_is_empty():
    _, player_id = create_team_and_player()

    result = database.get_player_relevant_boss_kc_summary(
        player_id
    )

    assert result == {
        "total_kc": 0,
        "bosses": []
    }


def test_relevant_xp_counts_duplicate_metric_once():
    _, player_id = create_team_and_player()

    first_tile_id = database.add_tile(
        "Gain 1m Mining XP",
        "EXPERIENCE",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Gain 1m Mining XP"
    )

    second_tile_id = database.add_tile(
        "Gain Mining or Agility XP",
        "EXPERIENCE",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Gain Mining or Agility XP"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO tile_conditions (
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            )
            VALUES
                (%s, 1, 'EXPERIENCE', 'mining', 1000000),
                (%s, 1, 'EXPERIENCE', 'mining', 500000),
                (%s, 2, 'EXPERIENCE', 'agility', 500000)
            ''',
            (
                first_tile_id,
                second_tile_id,
                second_tile_id
            )
        )

    competition_id = 54321
    database.set_wom_competition_id(competition_id)

    set_wom_metric_gain(
        competition_id,
        player_id,
        "mining",
        250000
    )

    set_wom_metric_gain(
        competition_id,
        player_id,
        "agility",
        0
    )

    result = database.get_player_relevant_xp_summary(
        player_id
    )

    assert result == {
        "total_xp": 250000,
        "skills": [
            {
                "metric": "mining",
                "xp_gained": 250000,
                "related_tiles": [
                    "Gain 1m Mining XP",
                    "Gain Mining or Agility XP"
                ]
            }
        ]
    }


def test_relevant_xp_without_competition_is_empty():
    _, player_id = create_team_and_player()

    result = database.get_player_relevant_xp_summary(
        player_id
    )

    assert result == {
        "total_xp": 0,
        "skills": []
    }


def test_bingo_evidence_aggregates_dink_progress_by_event_and_tile():
    team_id, player_id = create_team_and_player(
        team_name="Bingo Evidence Dink Team",
        player_name="Bingo Evidence Dink Player"
    )

    tile_id = create_test_tile(
        "Bingo Evidence Dink Tile"
    )

    add_killcount_condition(
        tile_id,
        "bingo_evidence_first_metric",
        target=10,
        completion_path=1
    )
    add_killcount_condition(
        tile_id,
        "bingo_evidence_second_metric",
        target=20,
        completion_path=2
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                condition_id,
                completion_path
            FROM tile_conditions
            WHERE tile_id = %s
            ORDER BY completion_path
            ''',
            (tile_id,)
        )

        condition_rows = cursor.fetchall()

    assert len(condition_rows) == 2

    event_id = database.add_dink_event(
        event_fingerprint="player-data-bingo-evidence-aggregate",
        raw_payload={},
        player_name="Bingo Evidence Dink Player",
        player_id=player_id,
        event_type="KILLCOUNT",
        status="PROCESSED"
    )

    database.update_dink_event_screenshot(
        event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / f"dink_event_{event_id}.png"
        ).as_posix(),
        "bingo-evidence-test-sha"
    )

    rows_stored = database.add_dink_event_progress(
        event_id=event_id,
        trigger="bingo_evidence_test",
        amount=1,
        progress_results=[
            {
                "team_id": team_id,
                "condition_id": condition_rows[0][0],
                "tile_id": tile_id,
                "completion_path": condition_rows[0][1],
                "counted_amount": 0,
                "raw_progress": 1,
                "route_progress": 0.25,
                "credited": 0.25,
                "banked_total": 0.25,
                "ready": False,
                "completed": False
            },
            {
                "team_id": team_id,
                "condition_id": condition_rows[1][0],
                "tile_id": tile_id,
                "completion_path": condition_rows[1][1],
                "counted_amount": 0,
                "raw_progress": 1,
                "route_progress": 0.75,
                "credited": 0.75,
                "banked_total": 1.0,
                "ready": True,
                "completed": True
            }
        ]
    )

    assert rows_stored == 2

    database.add_completed_tile(
        tile_id,
        team_id
    )

    result = database.get_player_bingo_evidence(
        player_id
    )

    assert len(result) == 1

    evidence = result[0]

    assert evidence["tile_name"] == "Bingo Evidence Dink Tile"
    assert evidence["contribution"] == 1.0
    assert evidence["source"] == "Automatic submission"
    assert evidence["evidence_type"] == "dink"
    assert evidence["evidence_id"] == event_id
    assert evidence["status"] == "Tile completed"
    assert evidence["screenshot_path"].endswith(
        f"dink_event_{event_id}.png"
    )
    assert evidence["date"] is not None


def test_bingo_evidence_includes_accepted_manual_progress():
    _, player_id = create_team_and_player(
        team_name="Bingo Evidence Manual Team",
        player_name="Bingo Evidence Manual Player"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Bingo Evidence Manual Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Bingo Evidence Manual Drop",
                "target": 10
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "SUM",
                "route_target": 10
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            SELECT team_id
            FROM players
            WHERE player_id = %s
            ''',
            (player_id,)
        )

        team_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            INSERT INTO tile_condition_progress (
                team_id,
                condition_id,
                progress
            )
            VALUES (%s, %s, %s)
            ''',
            (
                team_id,
                condition_id,
                2
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=3,
        evidence_path="manual/bingo-evidence-accepted.png",
        evidence_sha256="b" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    review_result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert review_result["status"] == "ACCEPTED"
    assert review_result["actual_contribution"] == 0.3
    assert review_result["completed"] is False

    result = database.get_player_bingo_evidence(
        player_id
    )

    assert len(result) == 1

    evidence = result[0]

    assert evidence["tile_name"] == "Bingo Evidence Manual Tile"
    assert evidence["contribution"] == 0.3
    assert evidence["source"] == "Manual evidence"
    assert evidence["evidence_type"] == "manual"
    assert evidence["evidence_id"] == submission["evidence_id"]
    assert evidence["status"] == "Accepted — progress recorded"
    assert evidence["screenshot_path"] == (
        "manual/bingo-evidence-accepted.png"
    )
    assert evidence["date"] is not None


def test_bingo_evidence_includes_rejected_manual_reason():
    _, player_id = create_team_and_player(
        team_name="Bingo Evidence Rejected Team",
        player_name="Bingo Evidence Rejected Player"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Bingo Evidence Rejected Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Bingo Evidence Rejected Drop",
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

    submission = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=1,
        evidence_path="manual/bingo-evidence-rejected.png",
        evidence_sha256="c" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    review_result = database.reject_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff",
        reason_code="INSUFFICIENT_EVIDENCE",
        reason="Screenshot does not show the required drop."
    )

    assert review_result["status"] == "REJECTED"

    result = database.get_player_bingo_evidence(
        player_id
    )

    assert len(result) == 1

    evidence = result[0]

    assert evidence["tile_name"] == "Bingo Evidence Rejected Tile"
    assert evidence["contribution"] is None
    assert evidence["source"] == "Manual evidence"
    assert evidence["evidence_type"] == "manual"
    assert evidence["evidence_id"] == submission["evidence_id"]
    assert evidence["status"] == (
        "Not accepted — "
        "Screenshot does not show the required drop."
    )
    assert evidence["screenshot_path"] == (
        "manual/bingo-evidence-rejected.png"
    )
    assert evidence["date"] is not None


def test_bingo_evidence_marks_accepted_manual_tile_completed():
    _, player_id = create_team_and_player(
        team_name="Bingo Evidence Completed Team",
        player_name="Bingo Evidence Completed Player"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Bingo Evidence Completed Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Bingo Evidence Completed Drop",
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

    submission = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=1,
        evidence_path="manual/bingo-evidence-completed.png",
        evidence_sha256="d" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    review_result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert review_result["status"] == "ACCEPTED"
    assert review_result["completed"] is True

    result = database.get_player_bingo_evidence(
        player_id
    )

    assert len(result) == 1

    evidence = result[0]

    assert evidence["tile_name"] == "Bingo Evidence Completed Tile"
    assert evidence["contribution"] == 1.0
    assert evidence["source"] == "Manual evidence"
    assert evidence["evidence_type"] == "manual"
    assert evidence["evidence_id"] == submission["evidence_id"]
    assert evidence["status"] == "Accepted — tile completed"
    assert evidence["screenshot_path"] == (
        "manual/bingo-evidence-completed.png"
    )
    assert evidence["date"] is not None


def test_bingo_evidence_marks_incomplete_dink_progress_in_progress():
    team_id, player_id = create_team_and_player(
        team_name="Bingo Evidence In Progress Team",
        player_name="Bingo Evidence In Progress Player"
    )

    tile_id = create_test_tile(
        "Bingo Evidence In Progress Tile"
    )

    add_killcount_condition(
        tile_id,
        "bingo_evidence_in_progress_metric",
        target=10,
        completion_path=1
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

    event_id = database.add_dink_event(
        event_fingerprint="player-data-bingo-evidence-in-progress",
        raw_payload={},
        player_name="Bingo Evidence In Progress Player",
        player_id=player_id,
        event_type="KILLCOUNT",
        status="PROCESSED"
    )

    database.update_dink_event_screenshot(
        event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / f"dink_event_{event_id}.png"
        ).as_posix(),
        "bingo-evidence-in-progress-sha"
    )

    rows_stored = database.add_dink_event_progress(
        event_id=event_id,
        trigger="bingo_evidence_in_progress_metric",
        amount=2,
        progress_results=[
            {
                "team_id": team_id,
                "condition_id": condition_id,
                "tile_id": tile_id,
                "completion_path": 1,
                "counted_amount": 0,
                "raw_progress": 2,
                "route_progress": 0.2,
                "credited": 0.2,
                "banked_total": 0.2,
                "ready": False,
                "completed": False
            }
        ]
    )

    assert rows_stored == 1

    result = database.get_player_bingo_evidence(
        player_id
    )

    assert len(result) == 1

    evidence = result[0]

    assert evidence["tile_name"] == "Bingo Evidence In Progress Tile"
    assert evidence["contribution"] == 0.2
    assert evidence["source"] == "Automatic submission"
    assert evidence["evidence_type"] == "dink"
    assert evidence["evidence_id"] == event_id
    assert evidence["status"] == "In progress"
    assert evidence["date"] is not None


    database.add_completed_tile(
        tile_id,
        team_id
    )

    result = database.get_player_bingo_evidence(
        player_id
    )

    assert len(result) == 1
    assert result[0]["status"] == "Tile completed"


def test_bingo_evidence_completion_uses_frozen_dink_team_after_player_moves():
    original_team_id, player_id = create_team_and_player(
        team_name="Bingo Evidence Original Team",
        player_name="Bingo Evidence Moved Player"
    )

    database.add_team(
        "Bingo Evidence New Team",
        0,
        None
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT team_id
            FROM teams
            WHERE LOWER(team_name) = LOWER(%s)
            ''',
            ("Bingo Evidence New Team",)
        )

        new_team_id = cursor.fetchone()[0]

    tile_id = create_test_tile(
        "Bingo Evidence Frozen Team Tile"
    )

    add_killcount_condition(
        tile_id,
        "bingo_evidence_frozen_team_metric",
        target=10,
        completion_path=1
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

    event_id = database.add_dink_event(
        event_fingerprint="player-data-bingo-evidence-frozen-team",
        raw_payload={},
        player_name="Bingo Evidence Moved Player",
        player_id=player_id,
        event_type="KILLCOUNT",
        status="PROCESSED"
    )

    database.update_dink_event_screenshot(
        event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / f"dink_event_{event_id}.png"
        ).as_posix(),
        "bingo-evidence-frozen-team-sha"
    )

    rows_stored = database.add_dink_event_progress(
        event_id=event_id,
        trigger="bingo_evidence_frozen_team_metric",
        amount=10,
        progress_results=[
            {
                "team_id": original_team_id,
                "condition_id": condition_id,
                "tile_id": tile_id,
                "completion_path": 1,
                "counted_amount": 0,
                "raw_progress": 10,
                "route_progress": 1.0,
                "credited": 1.0,
                "banked_total": 1.0,
                "ready": True,
                "completed": True
            }
        ]
    )

    assert rows_stored == 1

    database.add_completed_tile(
        tile_id,
        original_team_id
    )

    database.change_player_team(
        player_id,
        new_team_id
    )

    result = database.get_player_bingo_evidence(
        player_id
    )

    assert len(result) == 1
    assert result[0]["status"] == "Tile completed"


def test_player_data_filters_missing_bingo_evidence_screenshots(
    client,
    monkeypatch
):
    player_name = "Bingo Evidence Filter Player"

    team_id, player_id = create_team_and_player(
        team_name="Bingo Evidence Filter Team",
        player_name=player_name
    )

    tile_id = create_test_tile(
        "Bingo Evidence Filter Tile"
    )

    with database.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tiles
                SET prestart_revealed = TRUE
                WHERE tile_id = %s
                """,
                (tile_id,)
            )

    add_killcount_condition(
        tile_id,
        "bingo_evidence_filter_metric",
        target=10,
        completion_path=1
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

    existing_event_id = database.add_dink_event(
        event_fingerprint="player-data-existing-screenshot",
        raw_payload={},
        player_name=player_name,
        player_id=player_id,
        event_type="KILLCOUNT",
        status="PROCESSED"
    )

    missing_event_id = database.add_dink_event(
        event_fingerprint="player-data-missing-screenshot",
        raw_payload={},
        player_name=player_name,
        player_id=player_id,
        event_type="KILLCOUNT",
        status="PROCESSED"
    )

    database.add_dink_event_progress(
        event_id=existing_event_id,
        trigger="bingo_evidence_filter_metric",
        amount=1,
        progress_results=[
            {
                "team_id": team_id,
                "condition_id": condition_id,
                "tile_id": tile_id,
                "completion_path": 1,
                "counted_amount": 0,
                "raw_progress": 1,
                "route_progress": 0.1,
                "credited": 0.1,
                "banked_total": 0.1,
                "ready": False,
                "completed": False
            }
        ]
    )

    database.add_dink_event_progress(
        event_id=missing_event_id,
        trigger="bingo_evidence_filter_metric",
        amount=1,
        progress_results=[
            {
                "team_id": team_id,
                "condition_id": condition_id,
                "tile_id": tile_id,
                "completion_path": 1,
                "counted_amount": 0,
                "raw_progress": 2,
                "route_progress": 0.2,
                "credited": 0.1,
                "banked_total": 0.2,
                "ready": False,
                "completed": False
            }
        ]
    )

    evidence_directory = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
    )
    evidence_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    existing_path = (
        evidence_directory
        / f"dink_event_{existing_event_id}.png"
    )

    existing_path.write_bytes(
        b"existing-bingo-evidence"
    )

    database.update_dink_event_screenshot(
        existing_event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / existing_path.name
        ).as_posix(),
        "existing-bingo-evidence-sha"
    )

    missing_relative_path = (
        Path("uploads")
        / "dink_evidence"
        / f"dink_event_{missing_event_id}.png"
    ).as_posix()

    database.update_dink_event_screenshot(
        missing_event_id,
        missing_relative_path,
        "missing-bingo-evidence-sha"
    )

    create_dashboard_user(
        "Bingo Evidence Filter Login",
        "test-password",
        player_id=player_id
    )

    login_response = login_dashboard_user(
        client,
        "Bingo Evidence Filter Login",
        "test-password"
    )

    assert login_response.status_code == 302

    captured = {}

    def capture_render_template(
        template_name,
        **context
    ):
        captured["template_name"] = template_name
        captured["context"] = context
        return "rendered"

    monkeypatch.setattr(
        "routes.user_routes.render_template",
        capture_render_template
    )

    try:
        response = client.get(
            f"/user/player/{player_name}"
        )

        assert response.status_code == 200
        assert captured["template_name"] == (
            "user_templates/player.html"
        )

        bingo_evidence = captured[
            "context"
        ]["bingo_evidence"]

        assert len(bingo_evidence) == 1
        assert (
            bingo_evidence[0]["evidence_id"]
            == existing_event_id
        )
        assert (
            bingo_evidence[0]["evidence_type"]
            == "dink"
        )

        evidence_ids = {
            evidence["evidence_id"]
            for evidence in bingo_evidence
        }

        assert missing_event_id not in evidence_ids

    finally:
        existing_path.unlink(
            missing_ok=True
        )


def test_dink_evidence_view_respects_player_ownership(client):
    _, first_player_id = create_team_and_player(
        team_name="Evidence Team One",
        player_name="Evidence Player One"
    )

    _, second_player_id = create_team_and_player(
        team_name="Evidence Team Two",
        player_name="Evidence Player Two"
    )

    first_event_id = database.add_dink_event(
        event_fingerprint="player-data-own-evidence",
        raw_payload={},
        player_name="Evidence Player One",
        player_id=first_player_id,
        event_type="LOOT",
        status="PROCESSED"
    )

    second_event_id = database.add_dink_event(
        event_fingerprint="player-data-other-evidence",
        raw_payload={},
        player_name="Evidence Player Two",
        player_id=second_player_id,
        event_type="LOOT",
        status="PROCESSED"
    )

    evidence_directory = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
    )
    evidence_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    first_path = (
        evidence_directory
        / f"dink_event_{first_event_id}.png"
    )
    second_path = (
        evidence_directory
        / f"dink_event_{second_event_id}.png"
    )

    first_path.write_bytes(b"player-one-evidence")
    second_path.write_bytes(b"player-two-evidence")

    database.update_dink_event_screenshot(
        first_event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / first_path.name
        ).as_posix(),
        "test-sha-first"
    )

    database.update_dink_event_screenshot(
        second_event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / second_path.name
        ).as_posix(),
        "test-sha-second"
    )

    try:
        create_dashboard_user(
            "Evidence Player Login",
            "test-password",
            player_id=first_player_id
        )

        login_response = login_dashboard_user(
            client,
            "Evidence Player Login",
            "test-password"
        )

        assert login_response.status_code == 302

        own_response = client.get(
            f"/user/player/evidence/dink/{first_event_id}"
        )

        assert own_response.status_code == 200
        assert own_response.data == b"player-one-evidence"
        own_response.close()

        other_response = client.get(
            f"/user/player/evidence/dink/{second_event_id}"
        )

        assert other_response.status_code == 404

        client.get("/logout")

        create_dashboard_user(
            "Evidence Admin",
            "test-password",
            account_role="ADMIN"
        )

        login_response = login_dashboard_user(
            client,
            "Evidence Admin",
            "test-password"
        )

        assert login_response.status_code == 302

        admin_response = client.get(
            f"/user/player/evidence/dink/{second_event_id}"
        )

        assert admin_response.status_code == 200
        assert admin_response.data == b"player-two-evidence"
        admin_response.close()

    finally:
        first_path.unlink(
            missing_ok=True
        )
        second_path.unlink(
            missing_ok=True
        )

def test_manual_evidence_view_respects_player_ownership(client):
    _, first_player_id = create_team_and_player(
        team_name="Manual Evidence Team One",
        player_name="Manual Evidence Player One"
    )

    _, second_player_id = create_team_and_player(
        team_name="Manual Evidence Team Two",
        player_name="Manual Evidence Player Two"
    )

    first_file = manual_evidence_files.save_manual_evidence_file(
        b"manual-player-one-evidence",
        "first-evidence.png"
    )

    second_file = manual_evidence_files.save_manual_evidence_file(
        b"manual-player-two-evidence",
        "second-evidence.png"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO manual_evidence (
                player_id,
                evidence_path,
                evidence_sha256,
                submission_source,
                submitter_id,
                submitter_name,
                status
            )
            VALUES (%s, %s, %s, 'DISCORD', %s, %s, 'ACCEPTED')
            RETURNING evidence_id
            ''',
            (
                first_player_id,
                first_file["evidence_path"],
                first_file["evidence_sha256"],
                1001,
                "Manual Evidence Submitter One"
            )
        )

        first_evidence_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            INSERT INTO manual_evidence (
                player_id,
                evidence_path,
                evidence_sha256,
                submission_source,
                submitter_id,
                submitter_name,
                status
            )
            VALUES (%s, %s, %s, 'DISCORD', %s, %s, 'ACCEPTED')
            RETURNING evidence_id
            ''',
            (
                second_player_id,
                second_file["evidence_path"],
                second_file["evidence_sha256"],
                1002,
                "Manual Evidence Submitter Two"
            )
        )

        second_evidence_id = cursor.fetchone()[0]

    try:
        create_dashboard_user(
            "Manual Evidence Player Login",
            "test-password",
            player_id=first_player_id
        )

        login_response = login_dashboard_user(
            client,
            "Manual Evidence Player Login",
            "test-password"
        )

        assert login_response.status_code == 302

        own_response = client.get(
            (
                "/user/player/evidence/manual/"
                f"{first_evidence_id}"
            )
        )

        assert own_response.status_code == 200
        assert (
            own_response.data
            == b"manual-player-one-evidence"
        )
        own_response.close()

        other_response = client.get(
            (
                "/user/player/evidence/manual/"
                f"{second_evidence_id}"
            )
        )

        assert other_response.status_code == 404

        client.get("/logout")

        create_dashboard_user(
            "Manual Evidence Admin",
            "test-password",
            account_role="ADMIN"
        )

        login_response = login_dashboard_user(
            client,
            "Manual Evidence Admin",
            "test-password"
        )

        assert login_response.status_code == 302

        admin_response = client.get(
            (
                "/user/player/evidence/manual/"
                f"{second_evidence_id}"
            )
        )

        assert admin_response.status_code == 200
        assert (
            admin_response.data
            == b"manual-player-two-evidence"
        )
        admin_response.close()

    finally:
        manual_evidence_files.delete_manual_evidence_file(
            first_file["evidence_path"]
        )
        manual_evidence_files.delete_manual_evidence_file(
            second_file["evidence_path"]
        )


def test_recorded_condition_progress_locks_tile_edit_and_delete():
    team_id, _ = create_team_and_player(
        team_name="Locked Progress Team",
        player_name="Locked Progress Player"
    )

    tile_id = create_test_tile(
        "Locked Progress Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="locked_progress_metric",
        target=100
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            INSERT INTO tile_condition_progress (
                team_id,
                condition_id,
                progress
            )
            VALUES (%s, %s, %s)
            ''',
            (
                team_id,
                condition_id,
                1
            )
        )

    with pytest.raises(
        ValueError,
        match="cannot be edited"
    ):
        database.update_tile_with_conditions(
            tile_id=tile_id,
            tile_name="Edited Locked Progress Tile",
            tile_points=0,
            tile_rules="Edited rules",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "KILLCOUNT",
                    "condition_trigger":
                        "locked_progress_metric",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL"
                }
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot be deleted"
    ):
        database.remove_tile(tile_id)


def test_pending_manual_evidence_locks_tile_edit_and_delete():
    _, player_id = create_team_and_player(
        team_name="Manual Evidence Lock Team",
        player_name="Manual Evidence Lock Player"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Evidence Lock Tile",
        tile_points=0,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger":
                    "Manual Evidence Lock Drop",
                "target": 100
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

    submission = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=1,
        description="Pending evidence locks this tile.",
        evidence_path="manual/pending-lock-test.png",
        evidence_sha256="a" * 64,
        submission_source="DISCORD",
        submitter_id=123456789,
        submitter_name="Lock Test Staff"
    )

    assert submission["status"] == "PENDING"

    with pytest.raises(
        ValueError,
        match="cannot be edited"
    ):
        database.update_tile_with_conditions(
            tile_id=tile_id,
            tile_name="Edited Manual Evidence Lock Tile",
            tile_points=0,
            tile_rules="Edited rules",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "KILLCOUNT",
                    "condition_trigger":
                        "manual_evidence_lock_metric",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL"
                }
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot be deleted"
    ):
        database.remove_tile(tile_id)


def test_dink_progress_locks_tile_edit_and_delete():
    _, player_id = create_team_and_player(
        team_name="Dink Progress Lock Team",
        player_name="Dink Progress Lock Player"
    )

    tile_id = create_test_tile(
        "Dink Progress Lock Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="dink_progress_lock_metric",
        target=100
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

    event_id = database.add_dink_event(
        event_fingerprint="dink-progress-lock-event",
        raw_payload={},
        player_name="Dink Progress Lock Player",
        player_id=player_id,
        event_type="LOOT",
        status="PROCESSED"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO dink_event_progress (
                event_id,
                condition_id,
                tile_id,
                completion_path,
                trigger,
                amount,
                raw_progress,
                route_progress,
                credited,
                banked_total,
                ready,
                completed
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ''',
            (
                event_id,
                condition_id,
                tile_id,
                1,
                "dink_progress_lock_metric",
                1,
                1,
                0.01,
                0.01,
                0.01,
                False,
                False
            )
        )

    with pytest.raises(
        ValueError,
        match="cannot be edited"
    ):
        database.update_tile_with_conditions(
            tile_id=tile_id,
            tile_name="Edited Dink Progress Lock Tile",
            tile_points=0,
            tile_rules="Edited rules",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "KILLCOUNT",
                    "condition_trigger":
                        "dink_progress_lock_metric",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL"
                }
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot be deleted"
    ):
        database.remove_tile(tile_id)


def test_partial_contribution_locks_tile_edit_and_delete():
    team_id, player_id = create_team_and_player(
        team_name="Partial Contribution Lock Team",
        player_name="Partial Contribution Lock Player"
    )

    tile_id = create_test_tile(
        "Partial Contribution Lock Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="partial_contribution_lock_metric",
        target=100
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO partial_completions (
                player_id,
                team_id,
                tile_id,
                partial_completion
            )
            VALUES (%s, %s, %s, %s)
            ''',
            (
                player_id,
                team_id,
                tile_id,
                0.25
            )
        )

    with pytest.raises(
        ValueError,
        match="cannot be edited"
    ):
        database.update_tile_with_conditions(
            tile_id=tile_id,
            tile_name="Edited Partial Contribution Lock Tile",
            tile_points=0,
            tile_rules="Edited rules",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "KILLCOUNT",
                    "condition_trigger":
                        "partial_contribution_lock_metric",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL"
                }
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot be deleted"
    ):
        database.remove_tile(tile_id)


def test_completed_tile_locks_tile_edit_and_delete():
    team_id, _ = create_team_and_player(
        team_name="Completed Tile Lock Team",
        player_name="Completed Tile Lock Player"
    )

    tile_id = create_test_tile(
        "Completed Tile Lock Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="completed_tile_lock_metric",
        target=100
    )

    database.add_completed_tile(
        tile_id,
        team_id
    )

    with pytest.raises(
        ValueError,
        match="cannot be edited"
    ):
        database.update_tile_with_conditions(
            tile_id=tile_id,
            tile_name="Edited Completed Tile Lock Tile",
            tile_points=0,
            tile_rules="Edited rules",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "KILLCOUNT",
                    "condition_trigger":
                        "completed_tile_lock_metric",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL"
                }
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot be deleted"
    ):
        database.remove_tile(tile_id)


def test_player_tile_credit_locks_tile_edit_and_delete():
    team_id, player_id = create_team_and_player(
        team_name="Player Credit Lock Team",
        player_name="Player Credit Lock Player"
    )

    tile_id = create_test_tile(
        "Player Credit Lock Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="player_credit_lock_metric",
        target=100
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO player_tile_credits (
                player_id,
                team_id,
                tile_id,
                contribution,
                points_awarded,
                credit_type,
                evidence_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                player_id,
                team_id,
                tile_id,
                0.25,
                0,
                "TILE_COMPLETION",
                None
            )
        )

    with pytest.raises(
        ValueError,
        match="cannot be edited"
    ):
        database.update_tile_with_conditions(
            tile_id=tile_id,
            tile_name="Edited Player Credit Lock Tile",
            tile_points=0,
            tile_rules="Edited rules",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "KILLCOUNT",
                    "condition_trigger":
                        "player_credit_lock_metric",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL"
                }
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot be deleted"
    ):
        database.remove_tile(tile_id)


def test_relevant_drop_locks_tile_edit_and_delete():
    team_id, player_id = create_team_and_player(
        team_name="Relevant Drop Lock Team",
        player_name="Relevant Drop Lock Player"
    )

    tile_id = create_test_tile(
        "Relevant Drop Lock Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="relevant_drop_lock_metric",
        target=100
    )

    database.add_relevant_drop(
        team_id,
        player_id,
        tile_id,
        "Relevant Drop Lock Tile",
        "Relevant Drop Lock Item",
        "Relevant Drop Lock Player",
        None
    )

    with pytest.raises(
        ValueError,
        match="cannot be edited"
    ):
        database.update_tile_with_conditions(
            tile_id=tile_id,
            tile_name="Edited Relevant Drop Lock Tile",
            tile_points=0,
            tile_rules="Edited rules",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "KILLCOUNT",
                    "condition_trigger":
                        "relevant_drop_lock_metric",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL"
                }
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot be deleted"
    ):
        database.remove_tile(tile_id)


def test_unused_tile_can_still_be_edited_and_deleted():
    tile_id = create_test_tile(
        "Unused Editable Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="unused_editable_metric",
        target=100
    )

    database.update_tile_with_conditions(
        tile_id=tile_id,
        tile_name="Edited Unused Tile",
        tile_points=3,
        tile_rules="Edited unused tile rules",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "KILLCOUNT",
                "condition_trigger":
                    "unused_editable_metric",
                "target": 100
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                tile_name,
                tile_points,
                tile_rules
            FROM tiles
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        updated_tile = cursor.fetchone()

    assert updated_tile is not None
    assert updated_tile[0] == "Edited Unused Tile"
    assert float(updated_tile[1]) == 3.0
    assert updated_tile[2] == "Edited unused tile rules"

    database.remove_tile(tile_id)

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT 1
            FROM tiles
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        deleted_tile = cursor.fetchone()

    assert deleted_tile is None


def test_locked_tile_delete_route_redirects_with_error(client):
    team_id, _ = create_team_and_player(
        team_name="Delete Route Lock Team",
        player_name="Delete Route Lock Player"
    )

    tile_id = create_test_tile(
        "Delete Route Lock Tile"
    )

    add_killcount_condition(
        tile_id=tile_id,
        metric="delete_route_lock_metric",
        target=100
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            INSERT INTO tile_condition_progress (
                team_id,
                condition_id,
                progress
            )
            VALUES (%s, %s, %s)
            ''',
            (
                team_id,
                condition_id,
                1
            )
        )

    create_dashboard_user(
        "Tile Delete Route Organiser",
        "test-password",
        account_role="ORGANISER"
    )

    login_response = login_dashboard_user(
        client,
        "Tile Delete Route Organiser",
        "test-password"
    )

    assert login_response.status_code == 302

    delete_response = client.post(
        f"/tile/tiles/delete/{tile_id}"
    )

    assert delete_response.status_code == 302
    assert delete_response.headers["Location"].endswith(
        "/tile/tiles"
    )

    with client.session_transaction() as session:
        flashes = session.get("_flashes", [])

    assert (
        "danger",
        (
            "This tile cannot be deleted because progress "
            "or evidence has already been recorded for it."
        )
    ) in flashes

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT tile_name
            FROM tiles
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        remaining_tile = cursor.fetchone()

    assert remaining_tile is not None
    assert remaining_tile[0] == "Delete Route Lock Tile"


@pytest.mark.parametrize("role,expected_status", [
    ("ORGANISER", 200),
    ("ADMIN", 404),
    ("PLAYER", 404),
])
def test_hidden_manual_evidence_requires_organiser(
    client, role, expected_status
):
    _, player_id = create_team_and_player(
        team_name="Hidden Evidence Team",
        player_name="Hidden Evidence Player"
    )
    tile_id = database.add_tile_with_conditions(
        "Concealed Evidence Objective",
        1,
        "Secret evidence requirements",
        [{"completion_path": 1, "condition_type": "MANUAL",
          "condition_trigger": None, "target": 1}]
    )

    saved = manual_evidence_files.save_manual_evidence_file(
        b"concealed-manual-evidence",
        "concealed-evidence.png"
    )

    try:
        with database.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO manual_evidence (
                        tile_id, player_id, evidence_path,
                        evidence_sha256, submission_source,
                        submitter_id, submitter_name, status
                    )
                    VALUES (%s, %s, %s, %s, 'DISCORD', %s, %s, 'ACCEPTED')
                    RETURNING evidence_id
                    """,
                    (
                        tile_id, player_id,
                        saved["evidence_path"],
                        saved["evidence_sha256"],
                        1001, "Hidden Evidence Submitter"
                    )
                )
                evidence_id = cursor.fetchone()[0]

        create_dashboard_user(
            "Hidden Evidence Login",
            "test-password",
            account_role=role,
            player_id=player_id if role == "PLAYER" else None
        )
        login_response = login_dashboard_user(
            client, "Hidden Evidence Login", "test-password"
        )
        assert login_response.status_code == 302

        response = client.get(
            f"/user/player/evidence/manual/{evidence_id}"
        )
        try:
            assert response.status_code == expected_status
            if expected_status == 200:
                assert response.data == b"concealed-manual-evidence"
        finally:
            response.close()
    finally:
        manual_evidence_files.delete_manual_evidence_file(
            saved["evidence_path"]
        )



@pytest.mark.parametrize("role,reveal_both,start_has_passed,expected_status", [
    ("ADMIN", False, False, 404),
    ("PLAYER", False, False, 404),
    ("ORGANISER", False, False, 200),
    ("ADMIN", True, False, 200),
    ("PLAYER", True, False, 200),
    ("ADMIN", False, True, 200),
    ("PLAYER", False, True, 200),
])
def test_dink_multi_tile_evidence_respects_concealment(
    client, role, reveal_both, start_has_passed, expected_status
):
    team_id, player_id = create_team_and_player(
        team_name="Multi Tile Evidence Team",
        player_name="Multi Tile Evidence Player"
    )

    tile_ids = []
    for index, name in enumerate(("Visible Objective", "Concealed Objective")):
        tile_ids.append(
            database.add_tile_with_conditions(
                name,
                1,
                "Confidential Dink requirements",
                [{
                    "completion_path": 1,
                    "condition_type": "DROP",
                    "condition_trigger": f"multi_tile_evidence_drop_{index}",
                    "target": 1
                }]
            )
        )

    event_id = database.add_dink_event(
        event_fingerprint="multi-tile-evidence-event",
        raw_payload={},
        player_name="Multi Tile Evidence Player",
        player_id=player_id,
        event_type="LOOT",
        status="PROCESSED"
    )

    with database.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO bingo_config (
                    config_id, wom_competition_starts_at
                )
                VALUES (1, NOW() + (%s * INTERVAL '1 day'))
                ON CONFLICT (config_id) DO UPDATE
                SET wom_competition_starts_at = EXCLUDED.wom_competition_starts_at
                """,
                (-1 if start_has_passed else 1,)
            )
            revealed_ids = (
                tile_ids if reveal_both else tile_ids[:1]
            )
            for tile_id in revealed_ids:
                cursor.execute(
                    """
                    UPDATE tiles
                    SET prestart_revealed = TRUE
                    WHERE tile_id = %s
                    """,
                    (tile_id,)
                )

            for index, tile_id in enumerate(tile_ids):
                cursor.execute(
                    """
                    SELECT condition_id
                    FROM tile_conditions
                    WHERE tile_id = %s
                    LIMIT 1
                    """,
                    (tile_id,)
                )
                condition_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO dink_event_progress (
                        event_id, team_id, condition_id, tile_id,
                        completion_path, trigger, amount,
                        raw_progress, route_progress, credited,
                        banked_total, ready, completed
                    )
                    VALUES (
                        %s, %s, %s, %s, 1, %s, 1,
                        1, 1, 1, 1, FALSE, FALSE
                    )
                    """,
                    (
                        event_id, team_id, condition_id, tile_id,
                        f"multi_tile_evidence_drop_{index}"
                    )
                )

    lifecycle = database.get_bingo_lifecycle_status()
    assert lifecycle["start_webhook_sent_at"] is None

    evidence_directory = (
        PROJECT_ROOT / "uploads" / "dink_evidence"
    )
    evidence_directory.mkdir(parents=True, exist_ok=True)

    screenshot_path = (
        evidence_directory / f"dink_event_{event_id}.png"
    )
    screenshot_path.write_bytes(b"multi-tile-screenshot")

    database.update_dink_event_screenshot(
        event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / screenshot_path.name
        ).as_posix(),
        "multi-tile-test-sha"
    )

    try:
        create_dashboard_user(
            "Multi Tile Evidence Login",
            "test-password",
            account_role=role,
            player_id=player_id if role == "PLAYER" else None
        )
        login_response = login_dashboard_user(
            client, "Multi Tile Evidence Login", "test-password"
        )
        assert login_response.status_code == 302

        response = client.get(
            f"/user/player/evidence/dink/{event_id}"
        )
        try:
            assert response.status_code == expected_status
            if expected_status == 200:
                assert response.data == b"multi-tile-screenshot"
        finally:
            response.close()
    finally:
        screenshot_path.unlink(missing_ok=True)



@pytest.mark.parametrize("role", [
    "ORGANISER",
    "ADMIN",
    "PLAYER",
])
def test_player_profile_conceals_dink_evidence(
    client, monkeypatch, role
):
    team_id, player_id = create_team_and_player(
        team_name="Concealed Profile Team",
        player_name="Concealed Profile Player"
    )

    tile_id = database.add_tile_with_conditions(
        "Secret Profile Objective",
        1,
        "Confidential objective requirements",
        [{
            "completion_path": 1,
            "condition_type": "DROP",
            "condition_trigger": "secret_profile_drop",
            "target": 1
        }]
    )

    event_id = database.add_dink_event(
        event_fingerprint="concealed-profile-event",
        raw_payload={},
        player_name="Concealed Profile Player",
        player_id=player_id,
        event_type="LOOT",
        status="PROCESSED"
    )

    with database.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT condition_id
                FROM tile_conditions
                WHERE tile_id = %s
                """,
                (tile_id,)
            )
            condition_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO dink_event_progress (
                    event_id, team_id, condition_id, tile_id,
                    completion_path, trigger, amount,
                    counted_amount, raw_progress, route_progress,
                    credited, banked_total, ready, completed
                )
                VALUES (
                    %s, %s, %s, %s, 1, %s, 1,
                    1, 1, 1, 1, 1, FALSE, FALSE
                )
                """,
                (
                    event_id, team_id, condition_id, tile_id,
                    "secret_profile_drop"
                )
            )

            cursor.execute(
                """
                INSERT INTO bingo_config (
                    config_id, wom_competition_starts_at
                )
                VALUES (1, NOW() + INTERVAL '1 day')
                ON CONFLICT (config_id) DO UPDATE
                SET wom_competition_starts_at =
                    EXCLUDED.wom_competition_starts_at
                """
            )

    evidence_directory = (
        PROJECT_ROOT / "uploads" / "dink_evidence"
    )
    evidence_directory.mkdir(parents=True, exist_ok=True)

    screenshot_path = (
        evidence_directory / f"dink_event_{event_id}.png"
    )
    screenshot_path.write_bytes(b"secret-profile-evidence")

    database.update_dink_event_screenshot(
        event_id,
        (
            Path("uploads")
            / "dink_evidence"
            / screenshot_path.name
        ).as_posix(),
        "secret-profile-test-sha"
    )

    try:
        create_dashboard_user(
            "Concealed Profile Login",
            "test-password",
            account_role=role,
            player_id=player_id if role == "PLAYER" else None
        )

        login_response = login_dashboard_user(
            client,
            "Concealed Profile Login",
            "test-password"
        )
        assert login_response.status_code == 302

        captured = {}

        def capture_render_template(template_name, **context):
            captured["template_name"] = template_name
            captured["context"] = context
            return "rendered"

        monkeypatch.setattr(
            "routes.user_routes.render_template",
            capture_render_template
        )

        response = client.get(
            "/user/player/Concealed Profile Player"
        )

        assert response.status_code == 200
        assert captured["template_name"] == (
            "user_templates/player.html"
        )

        evidence = captured["context"]["bingo_evidence"]

        if role == "ORGANISER":
            assert len(evidence) == 1
            assert evidence[0]["evidence_id"] == event_id
            assert evidence[0]["tile_name"] == (
                "Secret Profile Objective"
            )
        else:
            assert evidence == []
    finally:
        screenshot_path.unlink(missing_ok=True)



@pytest.mark.parametrize("role,revealed,expected_visible", [
    ("ORGANISER", False, True),
    ("ADMIN", False, False),
    ("PLAYER", False, False),
    ("ADMIN", True, True),
    ("PLAYER", True, True),
])
def test_player_profile_conceals_relevant_drops(
    client, monkeypatch, role, revealed, expected_visible
):
    team_id, player_id = create_team_and_player(
        team_name="Hidden Drop Profile Team",
        player_name="Hidden Drop Profile Player"
    )

    tile_id = database.add_tile_with_conditions(
        "Secret Drop Objective",
        1,
        "Confidential drop requirements",
        [{
            "completion_path": 1,
            "condition_type": "DROP",
            "condition_trigger": "secret_profile_relic",
            "target": 1
        }]
    )

    event_id = database.add_dink_event(
        event_fingerprint="hidden-drop-profile-event",
        raw_payload={},
        player_name="Hidden Drop Profile Player",
        player_id=player_id,
        event_type="LOOT",
        status="PROCESSED"
    )

    with database.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT condition_id FROM tile_conditions WHERE tile_id = %s",
                (tile_id,)
            )
            condition_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO dink_event_progress (
                    event_id, team_id, condition_id, tile_id,
                    completion_path, trigger, amount,
                    counted_amount, raw_progress, route_progress,
                    credited, banked_total, ready, completed
                )
                VALUES (
                    %s, %s, %s, %s, 1, %s, 1,
                    1, 1, 1, 1, 1, FALSE, FALSE
                )
                """,
                (
                    event_id, team_id, condition_id, tile_id,
                    "secret_profile_relic"
                )
            )

            cursor.execute(
                """
                INSERT INTO bingo_config (
                    config_id, wom_competition_starts_at
                )
                VALUES (1, NOW() + INTERVAL '1 day')
                ON CONFLICT (config_id) DO UPDATE
                SET wom_competition_starts_at =
                    EXCLUDED.wom_competition_starts_at
                """
            )

            if revealed:
                cursor.execute(
                    """
                    UPDATE tiles
                    SET prestart_revealed = TRUE
                    WHERE tile_id = %s
                    """,
                    (tile_id,)
                )

    raw_summary = database.get_player_relevant_drop_summary(
        player_id
    )
    assert raw_summary["drops"] == [
        {"drop_name": "secret_profile_relic", "quantity": 1}
    ]

    create_dashboard_user(
        "Hidden Drop Profile Login",
        "test-password",
        account_role=role,
        player_id=player_id if role == "PLAYER" else None
    )

    login_response = login_dashboard_user(
        client, "Hidden Drop Profile Login", "test-password"
    )
    assert login_response.status_code == 302

    captured = {}

    def capture_render_template(template_name, **context):
        captured.update(context)
        return "rendered"

    monkeypatch.setattr(
        "routes.user_routes.render_template",
        capture_render_template
    )

    response = client.get(
        "/user/player/Hidden Drop Profile Player"
    )
    assert response.status_code == 200

    summary = captured["relevant_drop_summary"]

    if expected_visible:
        assert summary["drops"] == [
            {"drop_name": "secret_profile_relic", "quantity": 1}
        ]
        assert summary["total_quantity"] == 1
    else:
        assert summary["drops"] == []
        assert summary["total_quantity"] == 0



@pytest.mark.parametrize(
    "condition_type,metric,gain,summary_key,list_key,total_key,gain_key",
    [
        (
            "KILLCOUNT", "brutus", 108,
            "relevant_boss_kc_summary", "bosses",
            "total_kc", "kc_gained"
        ),
        (
            "EXPERIENCE", "mining", 250000,
            "relevant_xp_summary", "skills",
            "total_xp", "xp_gained"
        ),
    ]
)
@pytest.mark.parametrize("role,revealed,expected_visible", [
    ("ORGANISER", False, True),
    ("ADMIN", False, False),
    ("PLAYER", False, False),
    ("ADMIN", True, True),
    ("PLAYER", True, True),
])
def test_player_profile_conceals_wom_summaries(
    client, monkeypatch, condition_type, metric, gain,
    summary_key, list_key, total_key, gain_key,
    role, revealed, expected_visible
):
    _, player_id = create_team_and_player(
        team_name="Hidden WOM Profile Team",
        player_name="Hidden WOM Profile Player"
    )

    tile_name = "Secret WOM Profile Objective"

    tile_id = database.add_tile_with_conditions(
        tile_name,
        1,
        "Confidential WOM requirements",
        [{
            "completion_path": 1,
            "condition_type": condition_type,
            "condition_trigger": metric,
            "target": gain * 10
        }]
    )

    competition_id = 987654
    database.set_wom_competition_id(competition_id)

    set_wom_metric_gain(
        competition_id,
        player_id,
        metric,
        gain
    )

    with database.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO bingo_config (
                    config_id, wom_competition_starts_at
                )
                VALUES (1, NOW() + INTERVAL '1 day')
                ON CONFLICT (config_id) DO UPDATE
                SET wom_competition_starts_at =
                    EXCLUDED.wom_competition_starts_at
                """
            )

            if revealed:
                cursor.execute(
                    """
                    UPDATE tiles
                    SET prestart_revealed = TRUE
                    WHERE tile_id = %s
                    """,
                    (tile_id,)
                )

    create_dashboard_user(
        "Hidden WOM Profile Login",
        "test-password",
        account_role=role,
        player_id=player_id if role == "PLAYER" else None
    )

    login_response = login_dashboard_user(
        client,
        "Hidden WOM Profile Login",
        "test-password"
    )
    assert login_response.status_code == 302

    captured = {}

    def capture_render_template(template_name, **context):
        captured.update(context)
        return "rendered"

    monkeypatch.setattr(
        "routes.user_routes.render_template",
        capture_render_template
    )

    response = client.get(
        "/user/player/Hidden WOM Profile Player"
    )
    assert response.status_code == 200

    summary = captured[summary_key]

    if expected_visible:
        assert summary[total_key] == gain
        assert summary[list_key] == [{
            "metric": metric,
            gain_key: gain,
            "related_tiles": [tile_name]
        }]
    else:
        assert summary[total_key] == 0
        assert summary[list_key] == []



@pytest.mark.parametrize("role,expected_status", [
    ("ORGANISER", 302),
    ("ADMIN", 403),
    ("PLAYER", 403),
])
def test_tile_visibility_settings_permissions_and_locked_progress(
    client, role, expected_status
):
    team_id, _ = create_team_and_player(
        team_name="Visibility Settings Team",
        player_name="Visibility Settings Player"
    )

    tile_id = create_test_tile(
        "Visibility Settings Objective"
    )

    add_killcount_condition(
        tile_id,
        "visibility_settings_lock_metric",
        target=100
    )

    with database.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT condition_id
                FROM tile_conditions
                WHERE tile_id = %s
                """,
                (tile_id,)
            )
            condition_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO tile_condition_progress (
                    team_id, condition_id, progress
                )
                VALUES (%s, %s, 1)
                """,
                (team_id, condition_id)
            )

            cursor.execute(
                """
                SELECT
                    tile_name, tile_rules,
                    prestart_revealed, hidden_message, hidden_teaser
                FROM tiles
                WHERE tile_id = %s
                """,
                (tile_id,)
            )
            original = cursor.fetchone()

    create_dashboard_user(
        "Visibility Settings Login",
        "test-password",
        account_role=role
    )

    login_response = login_dashboard_user(
        client,
        "Visibility Settings Login",
        "test-password"
    )
    assert login_response.status_code == 302

    response = client.post(
        f"/tile/tiles/visibility/{tile_id}",
        data={
            "prestart_revealed": "on",
            "hidden_message": "A mysterious challenge awaits.",
            "hidden_teaser": "Somewhere in Morytania"
        }
    )

    assert response.status_code == expected_status

    with database.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    tile_name, tile_rules,
                    prestart_revealed, hidden_message, hidden_teaser
                FROM tiles
                WHERE tile_id = %s
                """,
                (tile_id,)
            )
            updated = cursor.fetchone()

            cursor.execute(
                """
                SELECT progress
                FROM tile_condition_progress
                WHERE team_id = %s AND condition_id = %s
                """,
                (team_id, condition_id)
            )
            progress = cursor.fetchone()[0]

    assert progress == 1
    assert updated[:2] == original[:2]

    if role == "ORGANISER":
        assert updated[2:] == (
            True,
            "A mysterious challenge awaits.",
            "Somewhere in Morytania"
        )
    else:
        assert updated == original



def test_edit_tile_visibility_form_roundtrip(client):
    tile_id = create_test_tile(
        "Visibility Form Test Tile"
    )

    create_dashboard_user(
        "Visibility Form Organiser",
        "test-password",
        account_role="ORGANISER"
    )

    login_response = login_dashboard_user(
        client,
        "Visibility Form Organiser",
        "test-password"
    )
    assert login_response.status_code == 302

    edit_url = f"/tile/tiles/edit/{tile_id}"
    visibility_url = f"/tile/tiles/visibility/{tile_id}"

    response = client.get(edit_url)
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'id="tile_visibility_settings"' in html
    assert 'name="prestart_revealed"' in html
    assert 'name="hidden_message"' in html
    assert 'name="hidden_teaser"' in html

    response = client.post(
        visibility_url,
        data={
            "prestart_revealed": "on",
            "hidden_message": "The objective remains hidden.",
            "hidden_teaser": "An ancient forest awaits."
        }
    )
    assert response.status_code == 302

    response = client.get(edit_url)
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    visibility_form = html.split(
        'id="tile_visibility_settings"', 1
    )[1].split("</form>", 1)[0]

    assert ' checked' in visibility_form
    assert "The objective remains hidden." in visibility_form
    assert "An ancient forest awaits." in visibility_form

    response = client.post(
        visibility_url,
        data={
            "hidden_message": "",
            "hidden_teaser": ""
        }
    )
    assert response.status_code == 302

    tile = database.get_tile_by_id(tile_id)
    assert tile[11] is False
    assert tile[12] is None
    assert tile[13] is None

    response = client.get(edit_url)
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    visibility_form = html.split(
        'id="tile_visibility_settings"', 1
    )[1].split("</form>", 1)[0]

    assert "The objective remains hidden." not in visibility_form
    assert "An ancient forest awaits." not in visibility_form
    assert " checked" not in visibility_form
