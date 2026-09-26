import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import hashlib
import io
import json

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from routes import dink
from utils import database, db_entities
from main import create_app

TEST_DINK_INGEST_SECRET = "danbot-dink-test-secret"
TEST_DINK_ENDPOINT = (
    f"/dink/{TEST_DINK_INGEST_SECRET}"
)


@pytest.fixture(autouse=True)
def dink_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Dink regression tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv(
        "DINK_INGEST_SECRET",
        TEST_DINK_INGEST_SECRET
    )
    monkeypatch.setattr(
        dink,
        "is_dink_tracking_active",
        lambda: True
    )

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


def set_wom_competition_window(
    starts_at,
    ends_at
):
    database.import_wom_competition(
        123456,
        {
            "Dink Test Team": [
                "Dink Tester"
            ]
        },
        "Blackout Sky",
        {
            "dink tester": 987654
        },
        competition_starts_at=starts_at.isoformat(),
        competition_ends_at=ends_at.isoformat()
    )


def test_dink_tracking_inactive_without_wom_timing(
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    assert dink.is_dink_tracking_active() is False


def test_dink_tracking_inactive_before_competition_start(
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    now = datetime.now(
        timezone.utc
    )

    set_wom_competition_window(
        now + timedelta(hours=1),
        now + timedelta(hours=2)
    )

    assert dink.is_dink_tracking_active() is False


def test_dink_tracking_active_during_competition_window(
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    now = datetime.now(
        timezone.utc
    )

    set_wom_competition_window(
        now - timedelta(hours=1),
        now + timedelta(hours=1)
    )

    assert dink.is_dink_tracking_active() is True


def test_dink_tracking_inactive_after_competition_end(
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    now = datetime.now(
        timezone.utc
    )

    set_wom_competition_window(
        now - timedelta(hours=2),
        now - timedelta(hours=1)
    )

    assert dink.is_dink_tracking_active() is False


def test_dink_tracking_manual_false_overrides_active_competition(
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "FALSE"
    )

    now = datetime.now(
        timezone.utc
    )

    set_wom_competition_window(
        now - timedelta(hours=1),
        now + timedelta(hours=1)
    )

    assert dink.is_dink_tracking_active() is False


def test_dink_identity_links_after_three_distinct_events():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    dink_account_hash = "test-dink-hash-001"

    payloads = [
        {
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": "Goblin",
                "killCount": 1
            }
        },
        {
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": "Man",
                "killCount": 1
            }
        },
        {
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": "Spider",
                "killCount": 1
            }
        }
    ]

    first_result = dink.ingest_dink_event(payloads[0])
    second_result = dink.ingest_dink_event(payloads[1])
    third_result = dink.ingest_dink_event(payloads[2])

    assert first_result["status"] == "PENDING"
    assert first_result["observations"] == 1
    assert first_result["player_id"] is None

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2
    assert second_result["player_id"] is None

    assert third_result["status"] == "LINKED"
    assert third_result["observations"] == 3
    assert third_result["player_id"] == player.player_id

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    assert identity is not None
    assert identity[1] == player.player_id
    assert identity[2] == "Dink Tester"
    assert identity[3] == "LINKED"


def test_duplicate_event_does_not_count_towards_identity_linking():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-duplicate"

    first_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    }

    second_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    }

    first_result = dink.ingest_dink_event(first_payload)
    duplicate_result = dink.ingest_dink_event(first_payload)
    second_result = dink.ingest_dink_event(second_payload)

    assert first_result["status"] == "PENDING"
    assert first_result["observations"] == 1

    assert duplicate_result["status"] == "DUPLICATE"
    assert duplicate_result["player_id"] is None

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    assert identity is not None
    assert identity[1] is None
    assert identity[3] == "PENDING"


def test_linked_dink_identity_blocks_different_rsn_after_link():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    dink_account_hash = "test-dink-hash-rsn-change"

    for boss in ("Goblin", "Man", "Spider"):
        result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert result["status"] == "LINKED"
    assert result["player_id"] == player.player_id

    conflict_result = dink.ingest_dink_event({
        "playerName": "Different RSN",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Rat",
            "killCount": 1
        }
    })

    assert conflict_result["status"] == "CONFLICT"
    assert conflict_result["player_id"] is None
    assert conflict_result["observations"] is None

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    assert identity is not None
    assert identity[1] == player.player_id
    assert identity[2] == "Dink Tester"
    assert identity[3] == "LINKED"


def test_pending_relevant_drop_is_processed_when_identity_links():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Retrospective Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Retrospective Test Drop",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-retrospective"

    drop_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Retrospective Test Drop",
                    "quantity": 1
                }
            ]
        }
    })

    second_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    })

    third_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    })

    assert drop_result["status"] == "PENDING"
    assert drop_result["observations"] == 1

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2

    assert third_result["status"] == "LINKED"
    assert third_result["observations"] == 3

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    pending_events = database.get_pending_dink_events_by_hash(
        dink_account_hash
    )

    assert pending_events == []


def test_pending_irrelevant_event_is_ignored_when_identity_links():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    dink_account_hash = "test-dink-hash-pending-ignored"

    first_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    }

    first_result = dink.ingest_dink_event(first_payload)

    second_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    })

    third_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Spider",
            "killCount": 1
        }
    })

    assert first_result["status"] == "PENDING"
    assert second_result["status"] == "PENDING"
    assert third_result["status"] == "LINKED"

    first_fingerprint = dink.create_dink_event_fingerprint(
        first_payload
    )

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            first_fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == first_result["event_id"]
    assert stored_event[2] == "IGNORED"
    assert stored_event[3] == player.player_id
    assert stored_event[4] == dink_account_hash

    pending_events = database.get_pending_dink_events_by_hash(
        dink_account_hash
    )

    assert pending_events == []


def test_pending_relevant_pet_is_processed_when_identity_links():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Retrospective Pet Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "PET",
                "condition_trigger": "Retrospective Test Pet",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-retrospective-pet"

    pet_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "PET",
        "extra": {
            "petName": "Retrospective Test Pet"
        }
    }

    pet_result = dink.ingest_dink_event(
        pet_payload
    )

    second_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    })

    third_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    })

    assert pet_result["status"] == "PENDING"
    assert pet_result["observations"] == 1

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2

    assert third_result["status"] == "LINKED"
    assert third_result["observations"] == 3

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    pet_fingerprint = dink.create_dink_event_fingerprint(
        pet_payload
    )

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            pet_fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == pet_result["event_id"]
    assert stored_event[2] == "PROCESSED"


def test_linked_drop_processes_through_json_endpoint(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Endpoint Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Endpoint Test Drop",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-endpoint-drop"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        TEST_DINK_ENDPOINT,
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Endpoint Test Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["message"] == "Dink event received"
    assert response_data["identity_status"] == "LINKED"
    assert response_data["observations"] == 4
    assert response_data["processing_status"] == "PROCESSED"

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1


def test_linked_pet_processes_through_json_endpoint(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Endpoint Pet Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "PET",
                "condition_trigger": "Endpoint Test Pet",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-endpoint-pet"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        TEST_DINK_ENDPOINT,
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "PET",
            "extra": {
                "petName": "Endpoint Test Pet"
            }
        }
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["observations"] == 4
    assert response_data["processing_status"] == "PROCESSED"

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1


def test_irrelevant_linked_loot_is_ignored_through_endpoint(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-endpoint-ignored"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Completely Irrelevant Drop",
                    "quantity": 1
                }
            ]
        }
    }

    response = client.post(
        TEST_DINK_ENDPOINT,
        json=payload
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["observations"] == 4
    assert response_data["processing_status"] == "IGNORED"

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == response_data["event_id"]
    assert stored_event[2] == "IGNORED"


def test_multi_item_loot_scores_all_relevant_items(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    first_tile_id = database.add_tile_with_conditions(
        tile_name="Multi Item Drop A Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Multi Item Drop A",
                "target": 1
            }
        ]
    )

    second_tile_id = database.add_tile_with_conditions(
        tile_name="Multi Item Drop B Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Multi Item Drop B",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-multi-item"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        TEST_DINK_ENDPOINT,
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Multi Item Drop A",
                        "quantity": 1
                    },
                    {
                        "name": "Coins",
                        "quantity": 57
                    },
                    {
                        "name": "Multi Item Drop B",
                        "quantity": 2
                    }
                ]
            }
        }
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["processing_status"] == "PROCESSED"

    first_completions = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            first_tile_id
        )
    )

    second_completions = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            second_tile_id
        )
    )

    assert len(first_completions) == 1
    assert len(second_completions) == 1

    audit_rows = database.get_dink_event_progress_by_event_id(
        response_data["event_id"]
    )

    assert len(audit_rows) == 2

    audit_triggers = {
        row[5]: row[6]
        for row in audit_rows
    }

    assert audit_triggers == {
        "Multi Item Drop A": 1,
        "Multi Item Drop B": 2
    }

    assert "Coins" not in audit_triggers


def test_duplicate_drop_trigger_is_rejected_across_tiles():
    database.add_tile_with_conditions(
        tile_name="Duplicate Drop Source Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Duplicate Setup Drop",
                "target": 1
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match=(
            "DROP trigger 'Duplicate Setup Drop' is already "
            "used by tile 'Duplicate Drop Source Tile'."
        )
    ):
        database.add_tile_with_conditions(
            tile_name="Duplicate Drop Blocked Tile",
            tile_points=1,
            tile_rules="",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "DROP",
                    "condition_trigger": "Duplicate Setup Drop",
                    "target": 1
                }
            ]
        )


def test_duplicate_drop_trigger_is_rejected_within_same_tile():
    with pytest.raises(
        ValueError,
        match=(
            "DROP trigger 'Same Tile Duplicate Drop' is already "
            "used more than once on this tile."
        )
    ):
        database.add_tile_with_conditions(
            tile_name="Same Tile Duplicate Drop Tile",
            tile_points=1,
            tile_rules="",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "DROP",
                    "condition_trigger": "Same Tile Duplicate Drop",
                    "target": 1
                },
                {
                    "completion_path": 2,
                    "condition_type": "DROP",
                    "condition_trigger": "Same Tile Duplicate Drop",
                    "target": 1
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL",
                    "route_target": None,
                    "require_unique": False
                },
                {
                    "completion_path": 2,
                    "route_mode": "ALL",
                    "route_target": None,
                    "require_unique": False
                }
            ]
        )


def test_update_tile_rejects_duplicate_drop_trigger_from_other_tile():
    database.add_tile_with_conditions(
        tile_name="Existing Drop Trigger Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Existing Duplicate Drop",
                "target": 1
            }
        ]
    )

    editable_tile_id = database.add_tile_with_conditions(
        tile_name="Editable Drop Trigger Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Original Editable Drop",
                "target": 1
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match=(
            "DROP trigger 'Existing Duplicate Drop' is already "
            "used by tile 'Existing Drop Trigger Tile'."
        )
    ):
        database.update_tile_with_conditions(
            editable_tile_id,
            "Editable Drop Trigger Tile",
            1,
            "",
            [
                {
                    "completion_path": 1,
                    "condition_type": "DROP",
                    "condition_trigger": "Existing Duplicate Drop",
                    "target": 1
                }
            ]
        )


def test_duplicate_delivery_cannot_double_score(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Duplicate Protection Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Duplicate Test Drop",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-duplicate-score"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Duplicate Test Drop",
                    "quantity": 1
                }
            ]
        }
    }

    first_response = client.post(
        TEST_DINK_ENDPOINT,
        json=payload
    )

    duplicate_response = client.post(
        TEST_DINK_ENDPOINT,
        json=payload
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 200

    first_data = first_response.get_json()
    duplicate_data = duplicate_response.get_json()

    assert first_data["identity_status"] == "LINKED"
    assert first_data["processing_status"] == "PROCESSED"

    assert duplicate_data["identity_status"] == "DUPLICATE"
    assert duplicate_data["processing_status"] is None

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []

    first_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            first_data["event_id"]
        )
    )

    duplicate_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            duplicate_data["event_id"]
        )
    )

    assert len(first_audit_rows) == 1
    assert first_audit_rows[0][6] == 1

    assert duplicate_audit_rows == []


def test_stranded_received_event_recovers_on_retry(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Retry Recovery Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Retry Recovery Drop",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-retry-recovery"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"
    assert link_result["player_id"] == player.player_id

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Retry Recovery Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    stranded_event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash=dink_account_hash,
        player_name="Dink Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        TEST_DINK_ENDPOINT,
        json=payload
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "RETRY"
    assert response_data["processing_status"] == "PROCESSED"

    duplicate_event_id = response_data["event_id"]

    assert duplicate_event_id != stranded_event_id

    original_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            stranded_event_id
        )
    )

    duplicate_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            duplicate_event_id
        )
    )

    assert len(original_audit_rows) == 1
    assert original_audit_rows[0][5] == "Retry Recovery Drop"
    assert duplicate_audit_rows == []

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    stored_original = (
        database.get_recent_dink_event_by_fingerprint(
            fingerprint
        )
    )

    assert stored_original is not None
    assert stored_original[0] == stranded_event_id
    assert stored_original[2] == "PROCESSED"
    assert stored_original[3] == player.player_id


def test_retry_after_recovered_event_becomes_duplicate(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Recovered Retry Duplicate Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Recovered Retry Drop",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-recovered-duplicate"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Recovered Retry Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    stranded_event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash=dink_account_hash,
        player_name="Dink Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    recovery_response = client.post(
        TEST_DINK_ENDPOINT,
        json=payload
    )

    recovery_data = recovery_response.get_json()

    assert recovery_response.status_code == 200
    assert recovery_data["identity_status"] == "RETRY"
    assert recovery_data["processing_status"] == "PROCESSED"

    later_retry_response = client.post(
        TEST_DINK_ENDPOINT,
        json=payload
    )

    later_retry_data = later_retry_response.get_json()

    assert later_retry_response.status_code == 200
    assert later_retry_data["identity_status"] == "DUPLICATE"
    assert later_retry_data["processing_status"] is None

    original_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            stranded_event_id
        )
    )

    later_retry_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            later_retry_data["event_id"]
        )
    )

    assert len(original_audit_rows) == 1
    assert later_retry_audit_rows == []

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []


def test_dink_progress_transaction_rolls_back_on_error():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Atomic Rollback Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Atomic Test Drop",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-atomic"

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Atomic Test Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash=dink_account_hash,
        player_name="Dink Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    event_progress = [
        {
            "condition_type": "DROP",
            "trigger": "Atomic Test Drop",
            "amount": 1
        },
        {
            "condition_type": "EXPERIENCE",
            "trigger": "Attack",
            "amount": 1
        }
    ]

    with pytest.raises(
        ValueError,
        match="Event progress can only be applied"
    ):
        database.process_dink_event_progress(
            event_id=event_id,
            player_id=player.player_id,
            event_progress=event_progress
        )

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    assert len(condition_progress) == 1
    assert condition_progress[0][5] == 0

    audit_rows = database.get_dink_event_progress_by_event_id(
        event_id
    )

    assert audit_rows == []

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == event_id
    assert stored_event[2] == "RECEIVED"
    assert stored_event[3] == player.player_id


def test_invalidating_dink_completion_reopens_tile_and_reverses_awards():
    database.add_team(
        "Dink Invalidation Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Invalidation Team")
    )

    database.add_player(
        "Dink Invalidation Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            "Dink Invalidation Tester"
        )
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Dink Invalidation Tile",
        tile_points=6,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Invalidation Test Drop",
                "target": 1
            }
        ]
    )

    payload = {
        "playerName": "Dink Invalidation Tester",
        "dinkAccountHash": "test-dink-invalidation-hash",
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Invalidation Test Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash="test-dink-invalidation-hash",
        player_name="Dink Invalidation Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    database.process_dink_event_progress(
        event_id=event_id,
        player_id=player.player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Invalidation Test Drop",
                "amount": 1
            }
        ]
    )

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team.team_id,)
        )

        assert float(cursor.fetchone()[0]) == 6.0

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player.player_id,)
        )

        player_points, tiles_completed = cursor.fetchone()

        assert float(player_points) == 6.0
        assert float(tiles_completed) == 1.0

    database.invalidate_bingo_evidence(
        subject_type="DINK_EVENT",
        subject_id=event_id,
        reason_code="INCORRECT_EVIDENCE",
        review_source="DISCORD",
        reviewer_id=987654321,
        reviewer_name="Invalidation Reviewer",
        details="Automated invalidation test."
    )

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    assert len(condition_progress) == 1
    assert float(condition_progress[0][5]) == 0.0

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[2] == "PROCESSED"

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team.team_id,)
        )

        assert float(cursor.fetchone()[0]) == 0.0

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player.player_id,)
        )

        player_points, tiles_completed = cursor.fetchone()

        assert float(player_points) == 0.0
        assert float(tiles_completed) == 0.0

        cursor.execute(
            '''
            SELECT
                reason_code,
                review_source,
                reviewer_id,
                reviewer_name,
                details
            FROM evidence_invalidations
            WHERE subject_type = 'DINK_EVENT'
              AND subject_id = %s
            ''',
            (event_id,)
        )

        assert cursor.fetchone() == (
            "INCORRECT_EVIDENCE",
            "DISCORD",
            987654321,
            "Invalidation Reviewer",
            "Automated invalidation test."
        )


def test_invalidating_bad_dink_replays_later_suppressed_dink_event():
    database.add_team(
        "Suppressed Dink Replay Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Suppressed Dink Replay Team"
        )
    )

    database.add_player(
        "Bad Suppressed Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    database.add_player(
        "Legit Suppressed Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    bad_player = db_entities.Player(
        database.get_player_by_name(
            "Bad Suppressed Dink Tester"
        )
    )

    legit_player = db_entities.Player(
        database.get_player_by_name(
            "Legit Suppressed Dink Tester"
        )
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Suppressed Dink Replay Tile",
        tile_points=6,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Suppressed Replay Drop",
                "target": 1
            }
        ]
    )

    bad_event_id = database.add_dink_event(
        event_fingerprint=(
            "bad-suppressed-dink-replay-event"
        ),
        raw_payload={
            "playerName": "Bad Suppressed Dink Tester",
            "type": "LOOT"
        },
        dink_account_hash=(
            "bad-suppressed-dink-replay-hash"
        ),
        player_name="Bad Suppressed Dink Tester",
        player_id=bad_player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    bad_result = database.process_dink_event_progress(
        event_id=bad_event_id,
        player_id=bad_player.player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Suppressed Replay Drop",
                "amount": 1
            }
        ]
    )

    assert bad_result["status"] == "PROCESSED"
    assert len(bad_result["progress"]) == 1
    assert bad_result["progress"][0]["completed"] is True

    legit_event_id = database.add_dink_event(
        event_fingerprint=(
            "legit-suppressed-dink-replay-event"
        ),
        raw_payload={
            "playerName": "Legit Suppressed Dink Tester",
            "type": "LOOT"
        },
        dink_account_hash=(
            "legit-suppressed-dink-replay-hash"
        ),
        player_name="Legit Suppressed Dink Tester",
        player_id=legit_player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    legit_result = database.process_dink_event_progress(
        event_id=legit_event_id,
        player_id=legit_player.player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Suppressed Replay Drop",
                "amount": 1
            }
        ]
    )

    # Evidence received while the tile is already complete must
    # remain replayable rather than being minimised as IGNORED.
    assert legit_result["status"] == "PROCESSED"
    assert len(legit_result["progress"]) == 1

    suppressed_result = legit_result["progress"][0]

    assert suppressed_result["state"] == (
        "SUPPRESSED_COMPLETED"
    )
    assert suppressed_result["counted_amount"] == 0
    assert suppressed_result["credited"] == 0.0
    assert suppressed_result["completed"] is False

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                state,
                counted_amount,
                credited,
                completed,
                condition_type_snapshot,
                condition_trigger_snapshot,
                condition_target_snapshot,
                route_mode_snapshot,
                route_target_snapshot,
                require_unique_snapshot
            FROM dink_event_progress
            WHERE event_id = %s
            ''',
            (legit_event_id,)
        )

        assert cursor.fetchone() == (
            "SUPPRESSED_COMPLETED",
            0,
            0,
            False,
            "DROP",
            "Suppressed Replay Drop",
            1,
            "ALL",
            None,
            False
        )

    invalidation_result = (
        database.invalidate_bingo_evidence(
            subject_type="DINK_EVENT",
            subject_id=bad_event_id,
            reason_code="INCORRECT_EVIDENCE",
            review_source="DISCORD",
            reviewer_id=987654321,
            reviewer_name="Invalidation Reviewer"
        )
    )

    # Removing the bad completion allows the later legitimate event
    # to replay immediately, so the tile's final state is completed
    # rather than reopened.
    assert invalidation_result["reopened_tiles"] == []

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                event_id,
                state,
                counted_amount,
                credited,
                completed
            FROM dink_event_progress
            WHERE event_id IN (%s, %s)
            ORDER BY event_id
            ''',
            (
                bad_event_id,
                legit_event_id
            )
        )

        progress_rows = cursor.fetchall()

        assert progress_rows == [
            (
                bad_event_id,
                "INVALIDATED",
                1,
                Decimal("1.000000000000"),
                True
            ),
            (
                legit_event_id,
                "APPLIED",
                1,
                Decimal("1.000000000000"),
                True
            )
        ]

        cursor.execute(
            '''
            SELECT
                points_awarded
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team.team_id,
                tile_id
            )
        )

        completion = cursor.fetchone()

        assert completion is not None
        assert float(completion[0]) == 6.0

        cursor.execute(
            '''
            SELECT progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = (
                  SELECT condition_id
                  FROM tile_conditions
                  WHERE tile_id = %s
              )
            ''',
            (
                team.team_id,
                tile_id
            )
        )

        assert cursor.fetchone()[0] == 1

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (bad_player.player_id,)
        )

        bad_totals = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (legit_player.player_id,)
        )

        legit_totals = cursor.fetchone()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team.team_id,)
        )

        team_points = cursor.fetchone()[0]

        cursor.execute(
            '''
            SELECT status
            FROM dink_events
            WHERE event_id = %s
            ''',
            (legit_event_id,)
        )

        legit_event_status = cursor.fetchone()[0]

    assert float(bad_totals[0]) == 0.0
    assert float(bad_totals[1]) == 0.0

    assert float(legit_totals[0]) == 6.0
    assert float(legit_totals[1]) == 1.0

    assert float(team_points) == 6.0

    # The event itself remains historically PROCESSED; its progress
    # row carries the scoring lifecycle.
    assert legit_event_status == "PROCESSED"

    assert database.get_player_relevant_drop_summary(
        bad_player.player_id
    )["total_quantity"] == 0

    assert database.get_player_relevant_drop_summary(
        legit_player.player_id
    )["total_quantity"] == 1


def test_invalidating_suppressed_dink_event_does_not_reverse_live_progress():
    database.add_team(
        "Suppressed Dink Invalidation Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Suppressed Dink Invalidation Team"
        )
    )

    database.add_player(
        "Original Suppressed Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    database.add_player(
        "Suppressed Invalidation Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    original_player = db_entities.Player(
        database.get_player_by_name(
            "Original Suppressed Dink Tester"
        )
    )

    suppressed_player = db_entities.Player(
        database.get_player_by_name(
            "Suppressed Invalidation Tester"
        )
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Suppressed Invalidation Tile",
        tile_points=5,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Suppressed Invalidation Drop",
                "target": 1
            }
        ]
    )

    original_event_id = database.add_dink_event(
        event_fingerprint=(
            "original-suppressed-invalidation-event"
        ),
        raw_payload={
            "playerName": "Original Suppressed Dink Tester",
            "type": "LOOT"
        },
        dink_account_hash=(
            "original-suppressed-invalidation-hash"
        ),
        player_name="Original Suppressed Dink Tester",
        player_id=original_player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    original_result = database.process_dink_event_progress(
        event_id=original_event_id,
        player_id=original_player.player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Suppressed Invalidation Drop",
                "amount": 1
            }
        ]
    )

    assert original_result["status"] == "PROCESSED"
    assert original_result["progress"][0]["completed"] is True

    suppressed_event_id = database.add_dink_event(
        event_fingerprint=(
            "suppressed-invalidation-event"
        ),
        raw_payload={
            "playerName": "Suppressed Invalidation Tester",
            "type": "LOOT"
        },
        dink_account_hash=(
            "suppressed-invalidation-hash"
        ),
        player_name="Suppressed Invalidation Tester",
        player_id=suppressed_player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    suppressed_result = database.process_dink_event_progress(
        event_id=suppressed_event_id,
        player_id=suppressed_player.player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Suppressed Invalidation Drop",
                "amount": 1
            }
        ]
    )

    assert suppressed_result["status"] == "PROCESSED"
    assert suppressed_result["progress"][0]["state"] == (
        "SUPPRESSED_COMPLETED"
    )
    assert suppressed_result["progress"][0]["counted_amount"] == 0
    assert suppressed_result["progress"][0]["credited"] == 0.0

    invalidation_result = database.invalidate_bingo_evidence(
        subject_type="DINK_EVENT",
        subject_id=suppressed_event_id,
        reason_code="INCORRECT_EVIDENCE",
        review_source="DISCORD",
        reviewer_id=987654321,
        reviewer_name="Invalidation Reviewer"
    )

    assert invalidation_result["status"] == "INVALIDATED"
    assert invalidation_result["reopened_tiles"] == []

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = (
                  SELECT condition_id
                  FROM tile_conditions
                  WHERE tile_id = %s
              )
            ''',
            (
                team.team_id,
                tile_id
            )
        )

        assert cursor.fetchone()[0] == 1

        cursor.execute(
            '''
            SELECT points_awarded
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team.team_id,
                tile_id
            )
        )

        assert cursor.fetchone()[0] == Decimal(
            "5.000000000000"
        )

        cursor.execute(
            '''
            SELECT
                event_id,
                state,
                counted_amount,
                credited,
                completed
            FROM dink_event_progress
            WHERE event_id IN (%s, %s)
            ORDER BY event_id
            ''',
            (
                original_event_id,
                suppressed_event_id
            )
        )

        assert cursor.fetchall() == [
            (
                original_event_id,
                "APPLIED",
                1,
                Decimal("1.000000000000"),
                True
            ),
            (
                suppressed_event_id,
                "INVALIDATED",
                0,
                Decimal("0E-12"),
                False
            )
        ]

        cursor.execute(
            '''
            SELECT player_points, tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (original_player.player_id,)
        )

        original_totals = cursor.fetchone()

        cursor.execute(
            '''
            SELECT player_points, tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (suppressed_player.player_id,)
        )

        suppressed_totals = cursor.fetchone()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team.team_id,)
        )

        team_points = cursor.fetchone()[0]

    assert float(original_totals[0]) == 5.0
    assert float(original_totals[1]) == 1.0

    assert float(suppressed_totals[0]) == 0.0
    assert float(suppressed_totals[1]) == 0.0

    assert float(team_points) == 5.0

    assert database.get_player_relevant_drop_summary(
        original_player.player_id
    )["total_quantity"] == 1

    assert database.get_player_relevant_drop_summary(
        suppressed_player.player_id
    )["total_quantity"] == 0


def test_invalidating_incomplete_dink_progress_removes_banked_contribution():
    database.add_team(
        "Incomplete Dink Invalidation Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Incomplete Dink Invalidation Team"
        )
    )

    database.add_player(
        "Incomplete Dink Invalidation Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            "Incomplete Dink Invalidation Tester"
        )
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Incomplete Dink Invalidation Tile",
        tile_points=6,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Incomplete Invalidation Drop",
                "target": 2
            }
        ]
    )

    payload = {
        "playerName": "Incomplete Dink Invalidation Tester",
        "dinkAccountHash": "test-incomplete-invalidation-hash",
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Incomplete Invalidation Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash="test-incomplete-invalidation-hash",
        player_name="Incomplete Dink Invalidation Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    result = database.process_dink_event_progress(
        event_id=event_id,
        player_id=player.player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Incomplete Invalidation Drop",
                "amount": 1
            }
        ]
    )

    assert result["status"] == "PROCESSED"
    assert len(result["progress"]) == 1
    assert result["progress"][0]["credited"] == 0.5
    assert result["progress"][0]["completed"] is False

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    assert len(condition_progress) == 1
    assert float(condition_progress[0][5]) == 1.0

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT partial_completion
            FROM partial_completions
            WHERE team_id = %s
              AND tile_id = %s
              AND player_id = %s
            ''',
            (
                team.team_id,
                tile_id,
                player.player_id
            )
        )

        assert float(cursor.fetchone()[0]) == 0.5

    database.invalidate_bingo_evidence(
        subject_type="DINK_EVENT",
        subject_id=event_id,
        reason_code="INCORRECT_EVIDENCE",
        review_source="WEB",
        reviewer_id=123456789,
        reviewer_name="Web Reviewer"
    )

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    assert len(condition_progress) == 1
    assert float(condition_progress[0][5]) == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT partial_completion
            FROM partial_completions
            WHERE team_id = %s
              AND tile_id = %s
              AND player_id = %s
            ''',
            (
                team.team_id,
                tile_id,
                player.player_id
            )
        )

        assert cursor.fetchone() is None

        cursor.execute(
            '''
            SELECT
                team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team.team_id,)
        )

        assert float(cursor.fetchone()[0]) == 0.0

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player.player_id,)
        )

        player_points, tiles_completed = cursor.fetchone()

        assert float(player_points) == 0.0
        assert float(tiles_completed) == 0.0

        cursor.execute(
            '''
            SELECT invalidation_id
            FROM evidence_invalidations
            WHERE subject_type = 'DINK_EVENT'
              AND subject_id = %s
            ''',
            (event_id,)
        )

        assert cursor.fetchone() is not None


def test_dink_invalidation_refuses_completed_tile_with_late_review_credit():
    database.add_team(
        "Dink Late Review Guard Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Dink Late Review Guard Team"
        )
    )

    database.add_player(
        "Dink Late Review Guard Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            "Dink Late Review Guard Tester"
        )
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Dink Late Review Guard Tile",
        tile_points=6,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Late Review Guard Drop",
                "target": 1
            }
        ]
    )

    payload = {
        "playerName": "Dink Late Review Guard Tester",
        "dinkAccountHash": "test-late-review-guard-hash",
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Late Review Guard Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash="test-late-review-guard-hash",
        player_name="Dink Late Review Guard Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    database.process_dink_event_progress(
        event_id=event_id,
        player_id=player.player_id,
        event_progress=[
            {
                "condition_type": "DROP",
                "trigger": "Late Review Guard Drop",
                "amount": 1
            }
        ]
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
            VALUES (
                %s,
                %s,
                %s,
                0.25,
                1.5,
                'LATE_REVIEW',
                999999
            )
            ''',
            (
                player.player_id,
                team.team_id,
                tile_id
            )
        )

        cursor.execute(
            '''
            UPDATE players
            SET
                tiles_completed =
                    COALESCE(tiles_completed, 0) + 0.25,
                player_points =
                    COALESCE(player_points, 0) + 1.5
            WHERE player_id = %s
            ''',
            (player.player_id,)
        )

        conn.commit()

    with pytest.raises(
        ValueError,
        match="late-review credit"
    ):
        database.invalidate_bingo_evidence(
            subject_type="DINK_EVENT",
            subject_id=event_id,
            reason_code="INCORRECT_EVIDENCE",
            review_source="DISCORD",
            reviewer_id=987654321,
            reviewer_name="Invalidation Reviewer"
        )

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    assert len(condition_progress) == 1
    assert float(condition_progress[0][5]) == 1.0

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team.team_id,)
        )

        assert float(cursor.fetchone()[0]) == 6.0

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player.player_id,)
        )

        player_points, tiles_completed = cursor.fetchone()

        assert float(player_points) == 7.5
        assert float(tiles_completed) == 1.25

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM player_tile_credits
            WHERE team_id = %s
              AND tile_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (
                team.team_id,
                tile_id
            )
        )

        assert cursor.fetchone()[0] == 1

        cursor.execute(
            '''
            SELECT invalidation_id
            FROM evidence_invalidations
            WHERE subject_type = 'DINK_EVENT'
              AND subject_id = %s
            ''',
            (event_id,)
        )

        assert cursor.fetchone() is None


def test_n_of_unique_does_not_count_same_item_twice(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Unique N Of Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Royal Item A",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Royal Item B",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Royal Item C",
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 2,
                "require_unique": True
            }
        ]
    )

    dink_account_hash = "test-dink-hash-n-of-unique"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    from utils import completion_notifications

    notified_completions = []

    def fake_notify_progress_completions(
        progress_results
    ):
        for progress_result in progress_results:
            if progress_result.get(
                "completed",
                False
            ):
                notified_completions.append(
                    (
                        progress_result["team_id"],
                        progress_result["tile_id"]
                    )
                )

    monkeypatch.setattr(
        completion_notifications,
        "notify_progress_completions",
        fake_notify_progress_completions
    )

    first_response = client.post(
        TEST_DINK_ENDPOINT,
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Royal Item A",
                        "quantity": 2
                    }
                ]
            }
        }
    )

    assert first_response.status_code == 200

    first_data = first_response.get_json()

    assert first_data["processing_status"] == "PROCESSED"

    first_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            first_data["event_id"]
        )
    )

    assert len(first_audit_rows) == 1
    assert first_audit_rows[0][14] == team.team_id
    assert first_audit_rows[0][15] == 1

    completed_after_first = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_after_first == []

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    progress_by_trigger = {
        row[3]: row[5]
        for row in condition_progress
    }

    assert progress_by_trigger["Royal Item A"] == 2
    assert progress_by_trigger["Royal Item B"] == 0
    assert progress_by_trigger["Royal Item C"] == 0

    second_response = client.post(
        TEST_DINK_ENDPOINT,
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Royal Item B",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    assert second_response.status_code == 200

    second_data = second_response.get_json()

    assert second_data["processing_status"] == "PROCESSED"

    completed_after_second = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_after_second) == 1

    assert notified_completions == [
        (
            team.team_id,
            tile_id
        )
    ]


def test_counted_drop_amount_caps_at_route_requirements():
    all_counted = database._calculate_counted_drop_amount(
        condition_type="DROP",
        amount=5,
        condition_target=10,
        condition_progress_before=8,
        route_state={
            "route_mode": "ALL",
            "current": 0,
            "target": 1
        }
    )

    sum_counted = database._calculate_counted_drop_amount(
        condition_type="DROP",
        amount=5,
        condition_target=999,
        condition_progress_before=0,
        route_state={
            "route_mode": "SUM",
            "current": 8,
            "target": 10
        }
    )

    non_unique_n_of_counted = (
        database._calculate_counted_drop_amount(
            condition_type="DROP",
            amount=5,
            condition_target=999,
            condition_progress_before=0,
            route_state={
                "route_mode": "N_OF",
                "current": 8,
                "target": 10,
                "require_unique": False
            }
        )
    )

    pet_counted = database._calculate_counted_drop_amount(
        condition_type="PET",
        amount=1,
        condition_target=1,
        condition_progress_before=0,
        route_state={
            "route_mode": "ALL",
            "current": 0,
            "target": 1
        }
    )

    assert all_counted == 2
    assert sum_counted == 2
    assert non_unique_n_of_counted == 2
    assert pet_counted == 0


def test_ignored_multipart_event_minimises_evidence(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-multipart-ignored"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Irrelevant Screenshot Drop",
                    "quantity": 1
                }
            ]
        }
    }

    screenshot_bytes = b"fake png evidence bytes"

    expected_sha256 = hashlib.sha256(
        screenshot_bytes
    ).hexdigest()

    response = client.post(
        TEST_DINK_ENDPOINT,
        data={
            "payload_json": json.dumps(payload),
            "file": (
                io.BytesIO(screenshot_bytes),
                "ignored-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["processing_status"] == "IGNORED"

    event_id = response_data["event_id"]

    stored_event = database.get_dink_event_by_id(
        event_id
    )

    assert stored_event is not None
    assert stored_event[0] == event_id
    assert stored_event[7] == {}
    assert stored_event[8] is None
    assert stored_event[9] == expected_sha256
    assert stored_event[10] == "IGNORED"

    expected_screenshot = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
        / f"dink_event_{event_id}.png"
    )

    assert not expected_screenshot.exists()


def test_duplicate_receipt_is_minimised(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-duplicate-minimised"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Duplicate Minimisation Drop",
                    "quantity": 1
                }
            ]
        }
    }

    screenshot_bytes = b"duplicate screenshot bytes"

    first_response = client.post(
        TEST_DINK_ENDPOINT,
        data={
            "payload_json": json.dumps(payload),
            "file": (
                io.BytesIO(screenshot_bytes),
                "duplicate-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    duplicate_response = client.post(
        TEST_DINK_ENDPOINT,
        data={
            "payload_json": json.dumps(payload),
            "file": (
                io.BytesIO(screenshot_bytes),
                "duplicate-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 200

    first_data = first_response.get_json()
    duplicate_data = duplicate_response.get_json()

    assert first_data["processing_status"] == "IGNORED"

    assert duplicate_data["identity_status"] == "DUPLICATE"
    assert duplicate_data["processing_status"] is None

    first_event = database.get_dink_event_by_id(
        first_data["event_id"]
    )

    duplicate_event = database.get_dink_event_by_id(
        duplicate_data["event_id"]
    )

    assert first_event is not None
    assert duplicate_event is not None

    assert first_event[7] == {}
    assert first_event[8] is None
    assert first_event[10] == "IGNORED"

    assert duplicate_event[2] == first_data["event_id"]
    assert duplicate_event[7] == {}
    assert duplicate_event[8] is None
    assert duplicate_event[10] == "IGNORED"


def test_dink_event_fingerprint_is_canonical_and_includes_screenshot():
    first_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": "test-dink-hash-fingerprint",
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Fingerprint Test Drop",
                    "quantity": 1
                }
            ]
        }
    }

    reordered_payload = {
        "extra": {
            "items": [
                {
                    "quantity": 1,
                    "name": "Fingerprint Test Drop"
                }
            ]
        },
        "type": "LOOT",
        "dinkAccountHash": "test-dink-hash-fingerprint",
        "playerName": "Dink Tester"
    }

    screenshot_sha256 = hashlib.sha256(
        b"first screenshot"
    ).hexdigest()

    different_screenshot_sha256 = hashlib.sha256(
        b"different screenshot"
    ).hexdigest()

    first_fingerprint = dink.create_dink_event_fingerprint(
        first_payload,
        screenshot_sha256
    )

    reordered_fingerprint = dink.create_dink_event_fingerprint(
        reordered_payload,
        screenshot_sha256
    )

    different_screenshot_fingerprint = (
        dink.create_dink_event_fingerprint(
            first_payload,
            different_screenshot_sha256
        )
    )

    assert first_fingerprint == reordered_fingerprint
    assert (
        first_fingerprint
        != different_screenshot_fingerprint
    )

def test_missing_dink_secret_is_rejected_and_audited(
    client,
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": "missing-secret-test-hash",
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Unauthorised Test Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "message": "Not found"
    }

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format
            FROM dink_auth_audit
            '''
        )

        audit_rows = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) FROM dink_events"
        )
        event_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM dink_identities"
        )
        identity_count = cursor.fetchone()[0]

    assert audit_rows == [
        (
            "MISSING_SECRET",
            "Dink Tester",
            "missing-secret-test-hash",
            "LOOT",
            "JSON"
        )
    ]

    assert event_count == 0
    assert identity_count == 0

def test_invalid_dink_secret_is_rejected_and_audited(
    client,
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink/not-the-correct-secret",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": "invalid-secret-test-hash",
            "type": "PET",
            "extra": {
                "petName": "Unauthorised Test Pet"
            }
        }
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "message": "Not found"
    }

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format
            FROM dink_auth_audit
            '''
        )

        audit_rows = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) FROM dink_events"
        )
        event_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM dink_identities"
        )
        identity_count = cursor.fetchone()[0]

    assert audit_rows == [
        (
            "INVALID_SECRET",
            "Dink Tester",
            "invalid-secret-test-hash",
            "PET",
            "JSON"
        )
    ]

    assert event_count == 0
    assert identity_count == 0

def test_missing_server_dink_secret_fails_closed_and_is_audited(
    client,
    monkeypatch
):
    monkeypatch.delenv(
        "DINK_INGEST_SECRET",
        raising=False
    )

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink/anything",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": "server-misconfigured-test-hash",
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Misconfigured Test Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "message": "Not found"
    }

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format
            FROM dink_auth_audit
            '''
        )

        audit_rows = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) FROM dink_events"
        )
        event_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM dink_identities"
        )
        identity_count = cursor.fetchone()[0]

    assert audit_rows == [
        (
            "SERVER_MISCONFIGURED",
            "Dink Tester",
            "server-misconfigured-test-hash",
            "LOOT",
            "JSON"
        )
    ]

    assert event_count == 0
    assert identity_count == 0

def test_invalid_dink_secret_does_not_save_screenshot(
    client,
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    evidence_directory = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
    )

    files_before = (
        set(evidence_directory.iterdir())
        if evidence_directory.exists()
        else set()
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": "invalid-multipart-test-hash",
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Unauthorised Screenshot Drop",
                    "quantity": 1
                }
            ]
        }
    }

    response = client.post(
        "/dink/not-the-correct-secret",
        data={
            "payload_json": json.dumps(payload),
            "file": (
                io.BytesIO(
                    b"unauthorised screenshot bytes"
                ),
                "unauthorised-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "message": "Not found"
    }

    files_after = (
        set(evidence_directory.iterdir())
        if evidence_directory.exists()
        else set()
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format
            FROM dink_auth_audit
            '''
        )

        audit_rows = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) FROM dink_events"
        )
        event_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM dink_identities"
        )
        identity_count = cursor.fetchone()[0]

    assert files_after == files_before

    assert audit_rows == [
        (
            "INVALID_SECRET",
            "Dink Tester",
            "invalid-multipart-test-hash",
            "LOOT",
            "MULTIPART"
        )
    ]

    assert event_count == 0
    assert identity_count == 0

def test_malformed_unauthorised_dink_request_is_audited(
    client,
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink/not-the-correct-secret",
        data={
            "payload_json": "{this is not valid json"
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "message": "Not found"
    }

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format
            FROM dink_auth_audit
            '''
        )

        audit_rows = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) FROM dink_events"
        )
        event_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM dink_identities"
        )
        identity_count = cursor.fetchone()[0]

    assert audit_rows == [
        (
            "INVALID_SECRET",
            None,
            None,
            None,
            "MULTIPART"
        )
    ]

    assert event_count == 0
    assert identity_count == 0

def test_valid_dink_secret_does_not_create_auth_audit(
    client,
    monkeypatch
):
    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        TEST_DINK_ENDPOINT,
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": "valid-secret-audit-test-hash",
            "type": "KILL_COUNT",
            "extra": {
                "boss": "Goblin",
                "killCount": 1
            }
        }
    )

    assert response.status_code == 200

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM dink_auth_audit"
        )
        audit_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM dink_events"
        )
        event_count = cursor.fetchone()[0]

    assert audit_count == 0
    assert event_count == 1
