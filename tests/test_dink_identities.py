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
from routes import dink
from utils import database


@pytest.fixture(autouse=True)
def dink_identity_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Dink identity tests must only run against "
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


def create_test_user(
    username,
    email,
    password,
    is_admin=False
):
    database.add_user(
        username,
        password
    )

    account_role = (
        "ADMIN"
        if is_admin
        else "PLAYER"
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET
                email = %s,
                account_role = %s
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            ''',
            (
                email,
                account_role,
                username
            )
        )


def login_test_user(
    client,
    email,
    password
):
    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT username
            FROM users
            WHERE LOWER(BTRIM(email))
                = LOWER(BTRIM(%s))
            ''',
            (email,)
        )

        username = cursor.fetchone()[0]

    return client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )


def create_test_player(
    player_name,
    team_name="Identity Test Team"
):
    database.add_team(
        team_name,
        0,
        ""
    )

    team = database.get_team_by_name(
        team_name
    )

    database.add_player(
        player_name,
        0,
        0,
        0,
        team[3],
        0
    )


def ingest_observation(
    player_name,
    dink_account_hash,
    boss
):
    return dink.ingest_dink_event(
        {
            "playerName": player_name,
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        }
    )


def login_admin(client):
    create_test_user(
        "Identity Admin",
        "identity-admin@example.test",
        "test-password",
        is_admin=True
    )

    response = login_test_user(
        client,
        "identity-admin@example.test",
        "test-password"
    )

    assert response.status_code == 302


def test_admin_can_view_pending_dink_identity(client):
    create_test_player(
        "Pending Tester"
    )

    ingest_observation(
        "Pending Tester",
        "pending-test-hash",
        "Goblin"
    )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Check Player Accounts" in page
    assert "Checking account" in page
    assert "Pending Tester" in page
    assert "Identity Test Team" in page
    assert "pending-test-hash" in page
    assert (
        "Seen 1 of 3 times needed "
        "for automatic matching"
    ) in page


def test_admin_can_view_linked_dink_identity(client):
    create_test_player(
        "Linked Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Linked Tester",
            "linked-test-hash",
            boss
        )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Account matched" in page
    assert "Account matched to a player" in page
    assert "Linked Tester" in page
    assert "Identity Test Team" in page
    assert "linked-test-hash" in page


def test_admin_sees_player_not_found_state(client):
    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Missing Tester",
            "missing-player-test-hash",
            boss
        )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Player not found" in page
    assert "Missing Tester" in page
    assert "missing-player-test-hash" in page
    assert (
        "Seen 3 or more times, but no matching "
        "bingo player was found"
    ) in page


def test_admin_sees_conflicting_rsn_reason(client):
    create_test_player(
        "Original Tester"
    )

    ingest_observation(
        "Original Tester",
        "rsn-conflict-test-hash",
        "Goblin"
    )

    ingest_observation(
        "Different Tester",
        "rsn-conflict-test-hash",
        "Man"
    )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Needs staff check" in page
    assert (
        "Different RuneScape names were seen "
        "for this account"
    ) in page
    assert "Original Tester" in page
    assert "Different Tester" in page
    assert "rsn-conflict-test-hash" in page


def test_admin_sees_existing_linked_hash_reason(client):
    create_test_player(
        "Double Hash Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Double Hash Tester",
            "primary-test-hash",
            boss
        )

    for boss in (
        "Rat",
        "Cow",
        "Chicken"
    ):
        ingest_observation(
            "Double Hash Tester",
            "secondary-test-hash",
            boss
        )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Needs staff check" in page
    assert (
        "Player is already matched to another "
        "RuneScape account"
    ) in page
    assert "primary-test-hash" in page
    assert "secondary-test-hash" in page

def test_manual_link_leaves_pending_events_unprocessed(client):
    create_test_player(
        "Manual Link Tester"
    )

    ingest_result = ingest_observation(
        "Manual Link Tester",
        "manual-link-test-hash",
        "Goblin"
    )

    player = database.get_player_by_name(
        "Manual Link Tester"
    )

    link_result = database.manually_link_dink_identity(
        "manual-link-test-hash",
        player[0]
    )

    assert link_result["status"] == "LINKED"
    assert link_result["player_id"] == player[0]

    identity = database.get_dink_identity_by_hash(
        "manual-link-test-hash"
    )

    assert identity is not None
    assert identity[1] == player[0]
    assert identity[3] == "LINKED"

    event = database.get_dink_event_by_id(
        ingest_result["event_id"]
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

def test_manual_link_refuses_second_hash_for_player(client):
    create_test_player(
        "Double Manual Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Double Manual Tester",
            "primary-manual-test-hash",
            boss
        )

    ingest_observation(
        "Double Manual Tester",
        "secondary-manual-test-hash",
        "Rat"
    )

    player = database.get_player_by_name(
        "Double Manual Tester"
    )

    link_result = database.manually_link_dink_identity(
        "secondary-manual-test-hash",
        player[0]
    )

    assert link_result["status"] == "PLAYER_ALREADY_LINKED"
    assert link_result["player_id"] == player[0]
    assert (
        link_result["existing_linked_hash"]
        == "primary-manual-test-hash"
    )

    primary_identity = database.get_dink_identity_by_hash(
        "primary-manual-test-hash"
    )

    secondary_identity = database.get_dink_identity_by_hash(
        "secondary-manual-test-hash"
    )

    assert primary_identity is not None
    assert primary_identity[1] == player[0]
    assert primary_identity[3] == "LINKED"

    assert secondary_identity is not None
    assert secondary_identity[1] is None
    assert secondary_identity[3] == "PENDING"
    assert secondary_identity[6] is None

def test_admin_can_manually_link_dink_identity(client):
    create_test_player(
        "Route Link Tester"
    )

    ingest_result = ingest_observation(
        "Route Link Tester",
        "route-link-test-hash",
        "Goblin"
    )

    player = database.get_player_by_name(
        "Route Link Tester"
    )

    login_admin(client)

    response = client.post(
        "/admin/dink_identities",
        data={
            "action": "manual_link",
            "dink_account_hash": "route-link-test-hash",
            "player_id": str(player[0])
        }
    )

    assert response.status_code == 302
    assert (
        response.headers["Location"]
        .endswith("/admin/dink_identities")
    )

    identity = database.get_dink_identity_by_hash(
        "route-link-test-hash"
    )

    assert identity is not None
    assert identity[1] == player[0]
    assert identity[3] == "LINKED"

    event = database.get_dink_event_by_id(
        ingest_result["event_id"]
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

def test_admin_manual_link_refuses_second_hash(client):
    create_test_player(
        "Route Double Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Route Double Tester",
            "route-primary-test-hash",
            boss
        )

    ingest_observation(
        "Route Double Tester",
        "route-secondary-test-hash",
        "Rat"
    )

    player = database.get_player_by_name(
        "Route Double Tester"
    )

    login_admin(client)

    response = client.post(
        "/admin/dink_identities",
        data={
            "action": "manual_link",
            "dink_account_hash": "route-secondary-test-hash",
            "player_id": str(player[0])
        }
    )

    assert response.status_code == 302
    assert (
        response.headers["Location"]
        .endswith("/admin/dink_identities")
    )

    primary_identity = database.get_dink_identity_by_hash(
        "route-primary-test-hash"
    )

    secondary_identity = database.get_dink_identity_by_hash(
        "route-secondary-test-hash"
    )

    assert primary_identity is not None
    assert primary_identity[1] == player[0]
    assert primary_identity[3] == "LINKED"

    assert secondary_identity is not None
    assert secondary_identity[1] is None
    assert secondary_identity[3] == "PENDING"


def test_pending_event_review_preserves_conflicting_claimed_rsns(client):
    create_test_player(
        "Real Review Tester",
        team_name="Conflict Review Team"
    )

    first_result = ingest_observation(
        "Real Review Tester",
        "conflict-review-event-hash",
        "Goblin"
    )

    second_result = ingest_observation(
        "Wrong Review Name",
        "conflict-review-event-hash",
        "Man"
    )

    player = database.get_player_by_name(
        "Real Review Tester"
    )

    link_result = database.manually_link_dink_identity(
        "conflict-review-event-hash",
        player[0]
    )

    assert first_result["status"] == "PENDING"
    assert second_result["status"] == "CONFLICT"
    assert link_result["status"] == "LINKED"

    review_rows = database.get_pending_dink_event_review_rows()

    assert len(review_rows) == 2

    assert review_rows[0][0] == first_result["event_id"]
    assert review_rows[0][2] == "Real Review Tester"
    assert review_rows[0][3] == "KILL_COUNT"
    assert review_rows[0][7] == "LINKED"
    assert review_rows[0][8] == "Real Review Tester"
    assert review_rows[0][9] == player[0]
    assert review_rows[0][10] == "Real Review Tester"
    assert review_rows[0][11] == "Conflict Review Team"

    assert review_rows[1][0] == second_result["event_id"]
    assert review_rows[1][2] == "Wrong Review Name"
    assert review_rows[1][3] == "KILL_COUNT"
    assert review_rows[1][7] == "LINKED"
    assert review_rows[1][8] == "Real Review Tester"
    assert review_rows[1][9] == player[0]
    assert review_rows[1][10] == "Real Review Tester"
    assert review_rows[1][11] == "Conflict Review Team"


def test_reject_pending_dink_event_marks_event_rejected(client):
    create_test_player(
        "Reject Tester",
        team_name="Reject Test Team"
    )

    ingest_result = ingest_observation(
        "Reject Tester",
        "reject-test-hash",
        "Goblin"
    )

    assert ingest_result["status"] == "PENDING"

    reject_result = database.reject_pending_dink_event(
        event_id=ingest_result["event_id"],
        review_source="WEB",
        reviewer_id=123,
        reviewer_name="Reject Test Admin",
        reason=(
            "Screenshot does not clearly show the drop."
        )
    )

    assert reject_result["status"] == "REJECTED"

    event = database.get_dink_event_by_id(
        ingest_result["event_id"]
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "REJECTED"
    assert event[12] is not None

    decision = database.get_staff_review_decision(
        "DINK_EVENT",
        ingest_result["event_id"]
    )

    assert decision is not None
    assert decision[1] == "DINK_EVENT"
    assert decision[2] == ingest_result["event_id"]
    assert decision[3] == "REJECT"
    assert decision[4] == "WEB"
    assert decision[5] == 123
    assert decision[6] == "Reject Test Admin"
    assert decision[7] == (
        "Screenshot does not clearly show the drop."
    )
    assert decision[8] is not None

    review_rows = database.get_pending_dink_event_review_rows()

    assert review_rows == []


def test_admin_can_view_historical_dink_event_review(client):
    create_test_player(
        "Historical Review Tester",
        team_name="Historical Review Team"
    )

    first_result = ingest_observation(
        "Historical Review Tester",
        "historical-review-test-hash",
        "Goblin"
    )

    second_result = ingest_observation(
        "Wrong Historical Name",
        "historical-review-test-hash",
        "Man"
    )

    player = database.get_player_by_name(
        "Historical Review Tester"
    )

    link_result = database.manually_link_dink_identity(
        "historical-review-test-hash",
        player[0]
    )

    assert first_result["status"] == "PENDING"
    assert second_result["status"] == "CONFLICT"
    assert link_result["status"] == "LINKED"

    login_admin(client)

    response = client.get(
        "/admin/dink_events"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Review Submissions" in page
    assert "#1" in page
    assert "#2" in page
    assert "Automatic submission" in page
    assert "Historical Review Tester" in page
    assert "Wrong Historical Name" in page
    assert "Historical Review Team" in page
    assert "historical-review-test-hash" in page


def test_admin_can_reject_historical_dink_event(client):
    create_test_player(
        "Admin Reject Tester",
        team_name="Admin Reject Team"
    )

    ingest_result = ingest_observation(
        "Admin Reject Tester",
        "admin-reject-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    login_admin(client)

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "reject_event",
            "event_id": str(event_id),
            "reason": "Screenshot does not clearly show the drop."
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        f"Submission #{event_id} was rejected."
        in page
    )

    event = database.get_dink_event_by_id(
        event_id
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "REJECTED"
    assert event[12] is not None

    decision = database.get_staff_review_decision(
        "DINK_EVENT",
        event_id
    )

    assert decision is not None
    assert decision[3] == "REJECT"
    assert decision[4] == "WEB"
    assert (
        decision[7]
        == "Screenshot does not clearly show the drop."
    )

    review_rows = (
        database.get_pending_dink_event_review_rows()
    )

    assert review_rows == []


def test_admin_cannot_reject_without_valid_reason(client):
    create_test_player(
        "Reject Reason Tester",
        team_name="Reject Reason Team"
    )

    ingest_result = ingest_observation(
        "Reject Reason Tester",
        "reject-reason-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    login_admin(client)

    for reason in ("", "No", "x" * 501):
        response = client.post(
            "/admin/dink_events",
            data={
                "action": "reject_event",
                "event_id": str(event_id),
                "reason": reason
            },
            follow_redirects=True
        )

        assert response.status_code == 200

        page = response.get_data(
            as_text=True
        )

        assert (
            "Please give a reason for rejecting this submission "
            "(3 to 500 characters)."
            in page
        )

        event = database.get_dink_event_by_id(
            event_id
        )

        assert event is not None
        assert event[10] == "PENDING_IDENTITY"
        assert event[12] is None

        decision = database.get_staff_review_decision(
            "DINK_EVENT",
            event_id
        )

        assert decision is None

def test_admin_can_accept_historical_dink_event(client):
    create_test_player(
        "Admin Accept Tester",
        team_name="Admin Accept Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Historical Accept Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Historical Accept Drop",
                "target": 1
            }
        ]
    )

    ingest_result = dink.ingest_dink_event(
        {
            "playerName": "Admin Accept Tester",
            "dinkAccountHash": "admin-accept-test-hash",
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Historical Accept Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    player = database.get_player_by_name(
        "Admin Accept Tester"
    )

    link_result = database.manually_link_dink_identity(
        "admin-accept-test-hash",
        player[0]
    )

    assert link_result["status"] == "LINKED"

    event_before = database.get_dink_event_by_id(
        event_id
    )

    assert event_before[10] == "PENDING_IDENTITY"
    assert event_before[5] is None

    login_admin(client)

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "accept_event",
            "event_id": str(event_id)
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        f"Submission #{event_id} was accepted "
        "and bingo progress was updated."
        in page
    )

    event_after = database.get_dink_event_by_id(
        event_id
    )

    assert event_after is not None
    assert event_after[5] == player[0]
    assert event_after[10] == "PROCESSED"
    assert event_after[12] is not None

    audit_rows = (
        database.get_dink_event_progress_by_event_id(
            event_id
        )
    )

    assert len(audit_rows) == 1

    team = database.get_team_by_name(
        "Admin Accept Team"
    )

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team[3],
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                player_id,
                team_id,
                tile_id,
                contribution,
                points_awarded,
                credit_type,
                evidence_id
            FROM player_tile_credits
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ''',
            (
                player[0],
                team[3],
                tile_id
            )
        )
        credit = cursor.fetchone()

    assert credit is not None
    assert credit[0] == player[0]
    assert credit[1] == team[3]
    assert credit[2] == tile_id
    assert float(credit[3]) == 1.0
    assert float(credit[4]) == 1.0
    assert credit[5] == "TILE_COMPLETION"
    assert credit[6] is None

    admin_user = database.get_user_by_email(
        "identity-admin@example.test"
    )

    assert admin_user is not None

    decision = database.get_staff_review_decision(
        "DINK_EVENT",
        event_id
    )

    assert decision is not None
    assert decision[1] == "DINK_EVENT"
    assert decision[2] == event_id
    assert decision[3] == "ACCEPT"
    assert decision[4] == "WEB"
    assert decision[5] == admin_user.id
    assert decision[6] == "Identity Admin"
    assert decision[7] is None
    assert decision[8] is not None

    review_rows = (
        database.get_pending_dink_event_review_rows()
    )

    assert review_rows == []


def test_tile_completion_can_return_detailed_allocation():
    create_test_player(
        "Detailed Completion Tester",
        team_name="Detailed Completion Team"
    )

    player = database.get_player_by_name(
        "Detailed Completion Tester"
    )

    assert player is not None

    detailed_tile_id = database.add_tile_with_conditions(
        tile_name="Detailed Completion Return Test",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    boolean_tile_id = database.add_tile_with_conditions(
        tile_name="Boolean Completion Return Test",
        tile_points=2,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
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
                player[0],
                player[5],
                detailed_tile_id,
                0.25
            )
        )

        detailed_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=player[5],
                tile_id=detailed_tile_id,
                finisher_player_id=player[0],
                return_details=True
            )
        )

        boolean_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=player[5],
                tile_id=boolean_tile_id,
                finisher_player_id=player[0]
            )
        )

        conn.commit()

    assert detailed_result["completed"] is True
    assert detailed_result["tile_points"] == 4.0

    assert detailed_result[
        "banked_total_before_finisher"
    ] == 0.25

    assert detailed_result["finisher_player_id"] == player[0]

    assert detailed_result["finisher_remainder"] == 0.75

    assert detailed_result["finisher_contribution"] == 1.0

    assert detailed_result["contributions"] == {
        player[0]: 1.0
    }

    assert boolean_result is True


def test_banked_contribution_stays_with_original_team():
    create_test_player(
        "Frozen Contribution Tester",
        team_name="Frozen Contribution Team A"
    )

    create_test_player(
        "Frozen Contribution Team B Member",
        team_name="Frozen Contribution Team B"
    )

    player = database.get_player_by_name(
        "Frozen Contribution Tester"
    )

    team_b_player = database.get_player_by_name(
        "Frozen Contribution Team B Member"
    )

    assert player is not None
    assert team_b_player is not None

    original_team_id = player[5]
    new_team_id = team_b_player[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Frozen Contribution Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
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
                player[0],
                original_team_id,
                tile_id,
                0.4
            )
        )

        conn.commit()

    database.change_player_team(
        player[0],
        new_team_id
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                team_id,
                tile_id,
                partial_completion
            FROM partial_completions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        moved_row = cursor.fetchone()

    assert moved_row is not None
    assert moved_row[0] == player[0]
    assert moved_row[1] == original_team_id
    assert moved_row[2] == tile_id
    assert float(moved_row[3]) == 0.4

    moved_player = database.get_player_by_name(
        "Frozen Contribution Tester"
    )

    assert moved_player is not None
    assert moved_player[5] == new_team_id

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            DELETE FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        conn.commit()

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                team_id,
                tile_id,
                partial_completion
            FROM partial_completions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        deleted_row = cursor.fetchone()

    assert deleted_row is not None
    assert deleted_row[0] is None
    assert deleted_row[1] == original_team_id
    assert deleted_row[2] == tile_id
    assert float(deleted_row[3]) == 0.4


def test_personal_credit_cap_is_separate_per_team():
    create_test_player(
        "Personal Credit Cap Tester",
        team_name="Personal Credit Team A"
    )

    create_test_player(
        "Personal Credit Team B Member",
        team_name="Personal Credit Team B"
    )

    player = database.get_player_by_name(
        "Personal Credit Cap Tester"
    )

    team_b_member = database.get_player_by_name(
        "Personal Credit Team B Member"
    )

    assert player is not None
    assert team_b_member is not None

    team_a_id = player[5]
    team_b_id = team_b_member[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Personal Credit Cap Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        # Team A:
        # 30% has already been finalised and another 40% is
        # currently banked, for a total personal credit of 70%.
        cursor.execute(
            '''
            INSERT INTO player_tile_credits (
                player_id,
                team_id,
                tile_id,
                contribution,
                points_awarded,
                credit_type
            )
            VALUES (%s, %s, %s, %s, %s, 'TILE_COMPLETION')
            ''',
            (
                player[0],
                team_a_id,
                tile_id,
                0.3,
                1.2
            )
        )

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
                player[0],
                team_a_id,
                tile_id,
                0.4
            )
        )

        # Team B deliberately exceeds 100% when its finalised
        # and banked values are combined. The helper should cap
        # this team's total at 1.0 without affecting Team A.
        cursor.execute(
            '''
            INSERT INTO player_tile_credits (
                player_id,
                team_id,
                tile_id,
                contribution,
                points_awarded,
                credit_type
            )
            VALUES (%s, %s, %s, %s, %s, 'TILE_COMPLETION')
            ''',
            (
                player[0],
                team_b_id,
                tile_id,
                0.8,
                3.2
            )
        )

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
                player[0],
                team_b_id,
                tile_id,
                0.4
            )
        )

        team_a_total = (
            database._get_player_team_tile_personal_credit_total(
                cursor=cursor,
                player_id=player[0],
                team_id=team_a_id,
                tile_id=tile_id
            )
        )

        team_b_total = (
            database._get_player_team_tile_personal_credit_total(
                cursor=cursor,
                player_id=player[0],
                team_id=team_b_id,
                tile_id=tile_id
            )
        )

        missing_player_total = (
            database._get_player_team_tile_personal_credit_total(
                cursor=cursor,
                player_id=None,
                team_id=team_a_id,
                tile_id=tile_id
            )
        )

        conn.rollback()

    assert team_a_total == 0.7
    assert team_b_total == 1.0
    assert missing_player_total == 0.0


def test_deleted_player_can_finish_tile_without_mvp_credit():
    create_test_player(
        "Deleted Finisher Live Contributor",
        team_name="Deleted Finisher Team"
    )

    player = database.get_player_by_name(
        "Deleted Finisher Live Contributor"
    )

    assert player is not None

    team_id = player[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Deleted Finisher Completion Test",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
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
                player[0],
                team_id,
                tile_id,
                0.6
            )
        )

        result = database._complete_tile_with_contributions(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            return_details=True,
            uncredited_finisher=True
        )

        conn.commit()

    assert result["completed"] is True
    assert result["tile_points"] == 4.0

    assert result["contributions"] == {
        player[0]: 0.6
    }

    assert result["banked_total_before_finisher"] == 0.6
    assert result["finisher_player_id"] is None
    assert result["finisher_remainder"] == 0.4
    assert result["finisher_contribution"] == 0.0
    assert result["uncredited_contribution"] == 0.4

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                contribution,
                points_awarded,
                credit_type
            FROM player_tile_credits
            WHERE team_id = %s
              AND tile_id = %s
            ORDER BY credit_id
            ''',
            (
                team_id,
                tile_id
            )
        )

        credits = cursor.fetchall()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team_id,)
        )

        team_points = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        completed_count = cursor.fetchone()[0]

    assert len(credits) == 1
    assert float(credits[0][0]) == 0.6
    assert float(credits[0][1]) == 2.4
    assert credits[0][2] == "TILE_COMPLETION"

    assert team_points == 4.0
    assert completed_count == 1


def test_admin_cannot_accept_unlinked_historical_dink_event(client):
    create_test_player(
        "Unlinked Accept Tester",
        team_name="Unlinked Accept Team"
    )

    ingest_result = dink.ingest_dink_event(
        {
            "playerName": "Unlinked Accept Tester",
            "dinkAccountHash": "unlinked-accept-test-hash",
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Unlinked Accept Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    login_admin(client)

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "accept_event",
            "event_id": str(event_id)
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        "This submission cannot be accepted until "
        "the RuneScape account has been checked."
        in page
    )

    event = database.get_dink_event_by_id(
        event_id
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

    audit_rows = (
        database.get_dink_event_progress_by_event_id(
            event_id
        )
    )

    assert audit_rows == []


def test_admin_can_view_dink_event_screenshot(client):
    create_test_player(
        "Screenshot Tester"
    )

    ingest_result = ingest_observation(
        "Screenshot Tester",
        "screenshot-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    screenshot_directory = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
    )

    screenshot_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    screenshot_file = (
        screenshot_directory
        / f"dink_event_{event_id}.png"
    )

    screenshot_file.unlink(
        missing_ok=True
    )

    response = None
    try:
        screenshot_file.write_bytes(
            b"Bingo bot screenshot regression test"
        )

        relative_path = (
            f"uploads/dink_evidence/"
            f"dink_event_{event_id}.png"
        )

        database.update_dink_event_screenshot(
            event_id,
            relative_path,
            "test-screenshot-sha256"
        )

        login_admin(client)

        response = client.get(
            f"/admin/dink_event/"
            f"{event_id}/screenshot"
        )

        assert response.status_code == 200
        assert (
            response.data
            == b"Bingo bot screenshot regression test"
        )

    finally:
        if response is not None:
            response.close()

        screenshot_file.unlink(
            missing_ok=True
        )


def test_dink_event_screenshot_rejects_path_outside_evidence_directory(
    client
):
    create_test_player(
        "Screenshot Path Tester"
    )

    ingest_result = ingest_observation(
        "Screenshot Path Tester",
        "screenshot-path-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    outside_file = (
        PROJECT_ROOT
        / "uploads"
        / f"dink_event_{event_id}.png"
    )

    outside_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    outside_file.unlink(
        missing_ok=True
    )

    response = None

    try:
        outside_file.write_bytes(
            b"This file must never be served"
        )

        unsafe_path = (
            f"uploads/dink_evidence/../"
            f"dink_event_{event_id}.png"
        )

        database.update_dink_event_screenshot(
            event_id,
            unsafe_path,
            "unsafe-test-sha256"
        )

        login_admin(client)

        response = client.get(
            f"/admin/dink_event/"
            f"{event_id}/screenshot"
        )

        assert response.status_code == 404

    finally:
        if response is not None:
            response.close()

        outside_file.unlink(
            missing_ok=True
        )


def test_non_admin_cannot_view_dink_event_screenshot(client):
    create_test_player(
        "Screenshot Access Tester"
    )

    ingest_result = ingest_observation(
        "Screenshot Access Tester",
        "screenshot-access-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    screenshot_directory = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
    )

    screenshot_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    screenshot_file = (
        screenshot_directory
        / f"dink_event_{event_id}.png"
    )

    screenshot_file.unlink(
        missing_ok=True
    )

    response = None

    try:
        screenshot_file.write_bytes(
            b"Private screenshot test"
        )

        database.update_dink_event_screenshot(
            event_id,
            (
                f"uploads/dink_evidence/"
                f"dink_event_{event_id}.png"
            ),
            "access-test-sha256"
        )

        create_test_user(
            "Screenshot User",
            "screenshot-user@example.test",
            "test-password"
        )

        login_response = login_test_user(
            client,
            "screenshot-user@example.test",
            "test-password"
        )

        assert login_response.status_code == 302

        response = client.get(
            f"/admin/dink_event/"
            f"{event_id}/screenshot"
        )

        assert response.status_code == 403

    finally:
        if response is not None:
            response.close()

        screenshot_file.unlink(
            missing_ok=True
        )


def test_non_admin_cannot_access_dink_events(client):
    create_test_player(
        "Dink Event Access Tester"
    )

    ingest_result = ingest_observation(
        "Dink Event Access Tester",
        "dink-event-access-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    create_test_user(
        "Dink Event User",
        "dink-event-user@example.test",
        "test-password"
    )

    login_response = login_test_user(
        client,
        "dink-event-user@example.test",
        "test-password"
    )

    assert login_response.status_code == 302

    get_response = client.get(
        "/admin/dink_events"
    )

    assert get_response.status_code == 403

    post_response = client.post(
        "/admin/dink_events",
        data={
            "action": "reject_event",
            "event_id": str(event_id)
        }
    )

    assert post_response.status_code == 403

    event = database.get_dink_event_by_id(
        event_id
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

def test_non_admin_cannot_view_dink_identities(client):
    create_test_user(
        "Identity User",
        "identity-user@example.test",
        "test-password"
    )

    login_response = login_test_user(
        client,
        "identity-user@example.test",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_view_dink_identities(
    client
):
    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_add_manual_evidence_derives_player_team_and_tile():
    create_test_player(
        "Manual Evidence Tester",
        team_name="Manual Evidence Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Evidence Test Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Manual Evidence Test Drop",
                "target": 3
            }
        ]
    )

    player = database.get_player_by_name(
        "Manual Evidence Tester"
    )

    assert player is not None

    conditions = database.get_tile_conditions(
        tile_id
    )

    assert len(conditions) == 1

    condition_id = conditions[0][0]

    database.set_evidence_codeword(
        "Test Evidence Word"
    )

    result = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=2,
        description="Two manual completions shown.",
        evidence_path="manual/test-evidence.png",
        evidence_sha256="a" * 64,
        submission_source="DISCORD",
        submitter_id=123456789,
        submitter_name="Test Staff",
        discord_guild_id=111,
        discord_channel_id=222,
        discord_message_id=333,
        evidence_author_id=444,
        evidence_author_name="Manual Evidence Tester"
    )

    assert result["status"] == "PENDING"
    assert result["player_id"] == player[0]
    assert result["team_id"] == player[5]
    assert result["tile_id"] == tile_id
    assert result["condition_id"] == condition_id
    assert result["amount"] == 2

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                player_id,
                credited_player_name,
                team_id,
                tile_id,
                condition_id,
                amount,
                evidence_codeword_at_submission,
                description,
                evidence_path,
                evidence_sha256,
                submission_source,
                submitter_id,
                submitter_name,
                discord_guild_id,
                discord_channel_id,
                discord_message_id,
                evidence_author_id,
                evidence_author_name,
                status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (result["evidence_id"],)
        )

        row = cursor.fetchone()

    assert row == (
        player[0],
        "Manual Evidence Tester",
        player[5],
        tile_id,
        condition_id,
        2,
        "Test Evidence Word",
        "Two manual completions shown.",
        "manual/test-evidence.png",
        "a" * 64,
        "DISCORD",
        123456789,
        "Test Staff",
        111,
        222,
        333,
        444,
        "Manual Evidence Tester",
        "PENDING"
    )


def test_pending_manual_evidence_review_rows_include_frozen_details():
    database.set_evidence_codeword(
        "Review Queue Word"
    )

    create_test_player(
        "Manual Review Tester",
        team_name="Manual Review Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Review Test Tile",
        tile_points=2,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Review Queue Drop",
                "target": 2
            }
        ]
    )

    player = database.get_player_by_name(
        "Manual Review Tester"
    )

    assert player is not None

    conditions = database.get_tile_conditions(
        tile_id
    )

    condition_id = conditions[0][0]

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=1,
        description="Review queue evidence.",
        evidence_path="manual/review-queue.png",
        evidence_sha256="b" * 64,
        submission_source="DISCORD",
        submitter_id=987654321,
        submitter_name="Review Staff"
    )

    review_rows = (
        database.get_pending_manual_evidence_review_rows()
    )

    review_row = next(
        row
        for row in review_rows
        if row["evidence_id"]
        == submission["evidence_id"]
    )

    assert review_row["credited_player_name"] == (
        "Manual Review Tester"
    )
    assert review_row["team_name"] == (
        "Manual Review Team"
    )
    assert review_row["tile_name"] == (
        "Manual Review Test Tile"
    )
    assert review_row["condition_id"] == condition_id
    assert review_row["completion_path"] == 1
    assert review_row["condition_type"] == "DROP"
    assert review_row["condition_trigger"] == (
        "Review Queue Drop"
    )
    assert review_row["condition_target"] == 2
    assert (
        review_row["condition_progress_at_submission"]
        == 0
    )
    assert review_row["amount"] == 1
    assert review_row["description"] == (
        "Review queue evidence."
    )
    assert review_row["submitter_id"] == 987654321
    assert review_row["submitter_name"] == (
        "Review Staff"
    )
    assert (
        review_row["evidence_codeword_at_submission"]
        == "Review Queue Word"
    )
    assert review_row["submitted_at"] is not None


def test_manual_evidence_freezes_full_tile_snapshot():
    create_test_player(
        "Manual Snapshot Tester",
        team_name="Manual Snapshot Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Snapshot Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Snapshot Drop A",
                "target": 2
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            },
            {
                "completion_path": 2,
                "condition_type": "METRIC",
                "condition_trigger": "snapshot_metric",
                "target": 10
            },
            {
                "completion_path": 2,
                "condition_type": "DROP",
                "condition_trigger": "Snapshot Drop B",
                "target": 5
            },
            {
                "completion_path": 3,
                "condition_type": "DROP",
                "condition_trigger": "Snapshot Unique A",
                "target": 1
            },
            {
                "completion_path": 3,
                "condition_type": "DROP",
                "condition_trigger": "Snapshot Unique B",
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            },
            {
                "completion_path": 2,
                "route_mode": "SUM",
                "route_target": 12
            },
            {
                "completion_path": 3,
                "route_mode": "N_OF",
                "route_target": 2,
                "require_unique": True
            }
        ]
    )

    player = database.get_player_by_name(
        "Manual Snapshot Tester"
    )

    assert player is not None

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                condition_id,
                condition_trigger
            FROM tile_conditions
            WHERE tile_id = %s
            ORDER BY condition_id
            ''',
            (tile_id,)
        )

        condition_rows = cursor.fetchall()

        condition_ids = {
            trigger: condition_id
            for condition_id, trigger in condition_rows
        }

        manual_condition_id = next(
            condition_id
            for condition_id, trigger in condition_rows
            if trigger is None
        )

        progress = {
            "Snapshot Drop A": 1,
            "snapshot_metric": 7,
            "Snapshot Drop B": 2,
            "Snapshot Unique A": 1
        }

        for trigger, amount in progress.items():
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
                    player[5],
                    condition_ids[trigger],
                    amount
                )
            )

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
                player[0],
                player[5],
                tile_id,
                0.35
            )
        )

        conn.commit()

    selected_condition_id = condition_ids[
        "Snapshot Drop B"
    ]

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=selected_condition_id,
        amount=3,
        description="Snapshot test evidence.",
        evidence_path="manual/snapshot-test.png",
        evidence_sha256="d" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Snapshot Staff"
    )

    assert submission["tile_points_at_submission"] == 4.0
    assert submission["banked_total_at_submission"] == 0.35

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                tile_points_at_submission,
                banked_total_at_submission,
                tile_name_at_submission
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        (
            frozen_points,
            frozen_banked_total,
            frozen_tile_name
        ) = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                completion_path,
                route_mode,
                route_target,
                require_unique
            FROM manual_evidence_path_snapshots
            WHERE evidence_id = %s
            ORDER BY completion_path
            ''',
            (submission["evidence_id"],)
        )

        path_snapshots = cursor.fetchall()

        cursor.execute(
            '''
            SELECT
                condition_id,
                completion_path,
                condition_type,
                condition_trigger,
                target,
                progress,
                selected_condition
            FROM manual_evidence_condition_snapshots
            WHERE evidence_id = %s
            ORDER BY condition_id
            ''',
            (submission["evidence_id"],)
        )

        condition_snapshots = cursor.fetchall()

    assert frozen_points == 4.0
    assert float(frozen_banked_total) == 0.35
    assert frozen_tile_name == "Manual Snapshot Test Tile"

    assert path_snapshots == [
        (1, "ALL", None, False),
        (2, "SUM", 12, False),
        (3, "N_OF", 2, True)
    ]

    snapshots_by_id = {
        row[0]: row[1:]
        for row in condition_snapshots
    }

    assert snapshots_by_id[
        condition_ids["Snapshot Drop A"]
    ] == (
        1,
        "DROP",
        "Snapshot Drop A",
        2,
        1,
        False
    )

    assert snapshots_by_id[
        manual_condition_id
    ] == (
        1,
        "MANUAL",
        None,
        1,
        0,
        False
    )

    assert snapshots_by_id[
        condition_ids["snapshot_metric"]
    ] == (
        2,
        "METRIC",
        "snapshot_metric",
        10,
        7,
        False
    )

    assert snapshots_by_id[
        selected_condition_id
    ] == (
        2,
        "DROP",
        "Snapshot Drop B",
        5,
        2,
        True
    )

    assert snapshots_by_id[
        condition_ids["Snapshot Unique A"]
    ] == (
        3,
        "DROP",
        "Snapshot Unique A",
        1,
        1,
        False
    )

    assert snapshots_by_id[
        condition_ids["Snapshot Unique B"]
    ] == (
        3,
        "DROP",
        "Snapshot Unique B",
        1,
        0,
        False
    )


def test_manual_evidence_checks_live_tile_compatibility():
    create_test_player(
        "Manual Compatibility Tester",
        team_name="Manual Compatibility Team"
    )

    player = database.get_player_by_name(
        "Manual Compatibility Tester"
    )

    assert player is not None

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Compatibility Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Compatibility Drop",
                "target": 2
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    conditions = database.get_tile_conditions(
        tile_id
    )

    assert len(conditions) == 1

    condition_id = conditions[0][0]

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=1,
        evidence_path="manual/compatibility-test.png",
        evidence_sha256="c" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Compatibility Staff"
    )

    evidence_id = submission["evidence_id"]

    with database.connect() as conn:
        cursor = conn.cursor()

        unchanged = (
            database._check_manual_evidence_live_compatibility(
                cursor=cursor,
                evidence_id=evidence_id,
                tile_id=tile_id
            )
        )

        assert unchanged["compatible"] is True
        assert unchanged["condition_id"] == condition_id
        assert unchanged["completion_path"] == 1
        assert unchanged["condition_type"] == "DROP"
        assert (
            unchanged["condition_trigger"]
            == "Compatibility Drop"
        )
        assert unchanged["target"] == 2
        assert unchanged["route_mode"] == "ALL"
        assert unchanged["route_target"] is None
        assert unchanged["require_unique"] is False

        cursor.execute(
            '''
            UPDATE tile_conditions
            SET target = 3
            WHERE condition_id = %s
            ''',
            (condition_id,)
        )

        changed_condition = (
            database._check_manual_evidence_live_compatibility(
                cursor=cursor,
                evidence_id=evidence_id,
                tile_id=tile_id
            )
        )

        assert changed_condition == {
            "compatible": False,
            "reason": "CONDITION_CHANGED",
            "message": (
                "This tile changed after the submission was "
                "made. The selected part is no longer the "
                "same, so it cannot be accepted normally."
            )
        }

        cursor.execute(
            '''
            UPDATE tile_conditions
            SET target = 2
            WHERE condition_id = %s
            ''',
            (condition_id,)
        )

        cursor.execute(
            '''
            UPDATE tile_completion_paths
            SET
                route_mode = 'SUM',
                route_target = 2
            WHERE tile_id = %s
              AND completion_path = 1
            ''',
            (tile_id,)
        )

        changed_path = (
            database._check_manual_evidence_live_compatibility(
                cursor=cursor,
                evidence_id=evidence_id,
                tile_id=tile_id
            )
        )

        assert changed_path == {
            "compatible": False,
            "reason": "PATH_CHANGED",
            "message": (
                "This tile changed after the submission was "
                "made. Its completion route is no longer the "
                "same, so it cannot be accepted normally."
            )
        }

        cursor.execute(
            '''
            UPDATE tile_completion_paths
            SET
                route_mode = 'ALL',
                route_target = NULL
            WHERE tile_id = %s
              AND completion_path = 1
            ''',
            (tile_id,)
        )

        cursor.execute(
            '''
            DELETE FROM tile_conditions
            WHERE condition_id = %s
            ''',
            (condition_id,)
        )

        deleted_condition = (
            database._check_manual_evidence_live_compatibility(
                cursor=cursor,
                evidence_id=evidence_id,
                tile_id=tile_id
            )
        )

        assert deleted_condition == {
            "compatible": False,
            "reason": "CONDITION_DELETED",
            "message": (
                "This tile changed after the submission was "
                "made. The selected part no longer exists, "
                "so it cannot be accepted normally."
            )
        }

        conn.rollback()


def test_incompatible_late_manual_evidence_accepts_for_audit_only():
    create_test_player(
        "Changed Late Evidence Tester",
        team_name="Changed Late Evidence Team"
    )

    create_test_player(
        "Changed Late Evidence Finisher",
        team_name="Changed Late Evidence Team"
    )

    player = database.get_player_by_name(
        "Changed Late Evidence Tester"
    )

    finisher = database.get_player_by_name(
        "Changed Late Evidence Finisher"
    )

    assert player is not None
    assert finisher is not None
    assert player[5] == finisher[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Changed Late Evidence Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Changed Late Drop",
                "target": 2
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    conditions = database.get_tile_conditions(tile_id)

    assert len(conditions) == 1

    condition_id = conditions[0][0]

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=1,
        evidence_path="manual/changed-late-test.png",
        evidence_sha256="1" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    # Under the frozen submission definition, one drop was worth
    # 50% of this two-drop ALL condition.
    assert submission["banked_total_at_submission"] == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        # The live tile definition changes incompatibly after the
        # evidence was submitted.
        cursor.execute(
            '''
            UPDATE tile_conditions
            SET target = 3
            WHERE condition_id = %s
            ''',
            (condition_id,)
        )

        # The changed live tile then completes through another
        # source before staff reviews the old evidence.
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
                player[5],
                condition_id,
                3
            )
        )

        completion_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=player[5],
                tile_id=tile_id,
                finisher_player_id=finisher[0],
                return_details=True
            )
        )

        assert completion_result["completed"] is True

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points_before_review = float(
            cursor.fetchone()[0]
        )

        conn.commit()

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff",
        award_lost_mvp=True
    )

    # Staff may still record genuinely valid old evidence as
    # accepted for audit, but the bingo bot must not score it against a
    # tile definition that no longer matches its frozen snapshot.
    assert result["status"] == "ACCEPTED"
    assert result["audit_only"] is True
    assert result["tile_changed"] is True
    assert result["compatibility_reason"] == "CONDITION_CHANGED"

    assert result["actual_contribution"] == 0.0
    assert result["normal_player_credit"] == 0.0
    assert result["lost_mvp_contribution"] == 0.0

    # Even though staff explicitly requested discretionary MVP,
    # an incompatible tile definition makes it ineligible.
    assert result["award_lost_mvp_requested"] is True
    assert result["late_review_contribution"] == 0.0
    assert result["late_review_points"] == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        evidence_status = cursor.fetchone()[0]

        cursor.execute(
            '''
            SELECT audit_only
            FROM staff_review_decisions
            WHERE subject_type = 'MANUAL_EVIDENCE'
              AND subject_id = %s
            ''',
            (submission["evidence_id"],)
        )

        persisted_audit_only = bool(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        late_credit_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT player_points
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        player_points = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points_after_review = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT
                decision,
                reason
            FROM staff_review_decisions
            WHERE subject_type = 'MANUAL_EVIDENCE'
              AND subject_id = %s
            ''',
            (submission["evidence_id"],)
        )

        decision_row = cursor.fetchone()

    assert evidence_status == "ACCEPTED"
    assert persisted_audit_only is True
    assert decision_row is not None
    assert decision_row[0] == "ACCEPT"
    assert decision_row[1] == (
        "Accepted for audit only because the tile "
        "changed after this submission was made. "
        "No points were awarded."
    )
    assert late_credit_count == 0
    assert player_points == 0.0

    # Review must not alter the score already earned by the live
    # version of the tile.
    assert team_points_before_review == 4.0
    assert team_points_after_review == 4.0

    bingo_evidence = database.get_player_bingo_evidence(
        player[0]
    )

    assert len(bingo_evidence) == 1

    evidence = bingo_evidence[0]

    assert evidence["evidence_type"] == "manual"
    assert evidence["evidence_id"] == submission["evidence_id"]
    assert evidence["source"] == "Manual evidence"
    assert evidence["contribution"] == 0.0
    assert evidence["status"] == "Accepted — audit only"
    assert evidence["date"] is not None


def test_manual_evidence_snapshot_route_evaluator():
    create_test_player(
        "Manual Snapshot Evaluator Tester",
        team_name="Manual Snapshot Evaluator Team"
    )

    player = database.get_player_by_name(
        "Manual Snapshot Evaluator Tester"
    )

    assert player is not None

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Snapshot Evaluator Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Evaluator All A",
                "target": 2
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Evaluator All B",
                "target": 2
            },
            {
                "completion_path": 2,
                "condition_type": "DROP",
                "condition_trigger": "Evaluator Sum",
                "target": 10
            },
            {
                "completion_path": 3,
                "condition_type": "DROP",
                "condition_trigger": "Evaluator Unique A",
                "target": 1
            },
            {
                "completion_path": 3,
                "condition_type": "DROP",
                "condition_trigger": "Evaluator Unique B",
                "target": 1
            },
            {
                "completion_path": 4,
                "condition_type": "DROP",
                "condition_trigger": "Evaluator Repeat",
                "target": 10
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            },
            {
                "completion_path": 2,
                "route_mode": "SUM",
                "route_target": 10
            },
            {
                "completion_path": 3,
                "route_mode": "N_OF",
                "route_target": 2,
                "require_unique": True
            },
            {
                "completion_path": 4,
                "route_mode": "N_OF",
                "route_target": 5,
                "require_unique": False
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                condition_id,
                condition_trigger
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_ids = {
            trigger: condition_id
            for condition_id, trigger
            in cursor.fetchall()
        }

        starting_progress = {
            "Evaluator All A": 1,
            "Evaluator Sum": 2,
            "Evaluator Unique B": 1,
            "Evaluator Repeat": 2
        }

        for trigger, progress in starting_progress.items():
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
                    player[5],
                    condition_ids[trigger],
                    progress
                )
            )

        conn.commit()

    def submit_evidence(
        trigger,
        amount,
        suffix
    ):
        return database.add_manual_evidence(
            player_id=player[0],
            condition_id=condition_ids[trigger],
            amount=amount,
            evidence_path=(
                f"manual/snapshot-evaluator-{suffix}.png"
            ),
            evidence_sha256=suffix * 64,
            submission_source="DISCORD",
            submitter_id=12345,
            submitter_name="Evaluator Staff"
        )

    all_submission = submit_evidence(
        "Evaluator All B",
        1,
        "a"
    )

    sum_submission = submit_evidence(
        "Evaluator Sum",
        3,
        "b"
    )

    unique_submission = submit_evidence(
        "Evaluator Unique A",
        1,
        "c"
    )

    repeat_submission = submit_evidence(
        "Evaluator Repeat",
        2,
        "d"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        all_result = (
            database._evaluate_manual_evidence_snapshot_route(
                cursor=cursor,
                evidence_id=all_submission["evidence_id"],
                amount=1
            )
        )

        sum_result = (
            database._evaluate_manual_evidence_snapshot_route(
                cursor=cursor,
                evidence_id=sum_submission["evidence_id"],
                amount=3
            )
        )

        adjusted_sum_result = (
            database._evaluate_manual_evidence_snapshot_route(
                cursor=cursor,
                evidence_id=sum_submission["evidence_id"],
                amount=3,
                progress_adjustments={
                    condition_ids["Evaluator Sum"]: 6
                }
            )
        )

        unique_result = (
            database._evaluate_manual_evidence_snapshot_route(
                cursor=cursor,
                evidence_id=unique_submission["evidence_id"],
                amount=1
            )
        )

        repeat_result = (
            database._evaluate_manual_evidence_snapshot_route(
                cursor=cursor,
                evidence_id=repeat_submission["evidence_id"],
                amount=2
            )
        )

        cursor.execute(
            '''
            SELECT progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                player[5],
                condition_ids["Evaluator Sum"]
            )
        )

        live_sum_progress = int(
            cursor.fetchone()[0]
        )

    assert all_result["route_mode"] == "ALL"
    assert all_result["before"]["progress_fraction"] == 0.25
    assert all_result["after"]["progress_fraction"] == 0.5
    assert all_result["route_contribution"] == 0.25

    assert sum_result["route_mode"] == "SUM"
    assert sum_result["before"]["progress_fraction"] == 0.2
    assert sum_result["after"]["progress_fraction"] == 0.5
    assert sum_result["route_contribution"] == 0.3

    # Replay 6 earlier units on the same SUM condition.
    # Frozen progress becomes 8/10 before this evidence, so
    # only the remaining 20% can still be contributed.
    assert (
        adjusted_sum_result["before"]["progress_fraction"]
        == 0.8
    )
    assert (
        adjusted_sum_result["after"]["progress_fraction"]
        == 1.0
    )
    assert adjusted_sum_result["route_contribution"] == 0.2

    assert unique_result["route_mode"] == "N_OF"
    assert unique_result["require_unique"] is True
    assert unique_result["before"]["progress_fraction"] == 0.5
    assert unique_result["after"]["progress_fraction"] == 1.0
    assert unique_result["route_contribution"] == 0.5

    assert repeat_result["route_mode"] == "N_OF"
    assert repeat_result["require_unique"] is False
    assert repeat_result["before"]["progress_fraction"] == 0.4
    assert repeat_result["after"]["progress_fraction"] == 0.8
    assert repeat_result["route_contribution"] == 0.4

    # Snapshot evaluation must never alter live bingo progress.
    assert live_sum_progress == 2


def test_manual_evidence_potential_respects_review_chronology():
    create_test_player(
        "Manual Potential Tester",
        team_name="Manual Potential Team"
    )

    player = database.get_player_by_name(
        "Manual Potential Tester"
    )

    assert player is not None

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Potential Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Potential Drop",
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

        # 35% of the tile's personal contribution had already
        # been earned before either submission was made.
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
                player[0],
                player[5],
                tile_id,
                0.35
            )
        )

        conn.commit()

    submission_a = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/potential-a.png",
        evidence_sha256="1" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Potential Staff"
    )

    # B is submitted while A is still pending. B therefore
    # freezes the board without A's progress or contribution.
    submission_b = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/potential-b.png",
        evidence_sha256="2" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Potential Staff"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        # Simulate A being accepted. Its raw +4 becomes live
        # progress and its 40% potential contribution becomes
        # banked contribution.
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
                player[5],
                condition_id,
                4
            )
        )

        contribution, banked_after = (
            database._bank_partial_contribution(
                cursor=cursor,
                player_id=player[0],
                team_id=player[5],
                tile_id=tile_id,
                requested_contribution=0.4
            )
        )

        assert contribution == 0.4
        assert banked_after == 0.75

        cursor.execute(
            '''
            UPDATE manual_evidence
            SET status = 'ACCEPTED'
            WHERE evidence_id = %s
            ''',
            (submission_a["evidence_id"],)
        )

        cursor.execute(
            '''
            INSERT INTO manual_evidence_progress (
                evidence_id,
                condition_id,
                tile_id,
                completion_path,
                amount,
                raw_progress,
                route_progress,
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution,
                banked_total,
                ready,
                completed
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ''',
            (
                submission_a["evidence_id"],
                condition_id,
                tile_id,
                1,
                4,
                4,
                0.4,
                0.4,
                0.0,
                0.4,
                0.4,
                0.0,
                0.75,
                False,
                False
            )
        )

        database._record_staff_review_decision(
            cursor=cursor,
            subject_type="MANUAL_EVIDENCE",
            subject_id=submission_a["evidence_id"],
            decision="ACCEPT",
            review_source="DISCORD",
            reviewer_id=54321,
            reviewer_name="Review Staff"
        )

        conn.commit()

    # C is submitted only after A has already been accepted.
    # Its frozen snapshot therefore already includes A and A
    # must not be replayed into C a second time.
    submission_c = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/potential-c.png",
        evidence_sha256="3" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Potential Staff"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        potential_b = (
            database
            ._calculate_manual_evidence_potential_contribution(
                cursor=cursor,
                evidence_id=submission_b["evidence_id"]
            )
        )

        potential_c = (
            database
            ._calculate_manual_evidence_potential_contribution(
                cursor=cursor,
                evidence_id=submission_c["evidence_id"]
            )
        )

    assert potential_b["available"] is True
    assert potential_b["banked_total_at_submission"] == 0.35

    assert potential_b["replayed_evidence_ids"] == [
        submission_a["evidence_id"]
    ]

    assert potential_b["progress_adjustments"] == {
        condition_id: 4
    }

    assert (
        potential_b["replayed_potential_contribution"]
        == 0.4
    )

    assert potential_b["hypothetical_banked_before"] == 0.75
    assert potential_b["remaining_personal_share"] == 0.25
    assert potential_b["route_contribution"] == 0.4
    assert potential_b["potential_contribution"] == 0.25

    # C was submitted after A's acceptance, so its own snapshot
    # already contains A. Replaying A again would double-count it.
    assert potential_c["available"] is True
    assert potential_c["banked_total_at_submission"] == 0.75
    assert potential_c["replayed_evidence_ids"] == []
    assert potential_c["progress_adjustments"] == {}
    assert (
        potential_c["replayed_potential_contribution"]
        == 0.0
    )

    assert potential_c["hypothetical_banked_before"] == 0.75
    assert potential_c["remaining_personal_share"] == 0.25
    assert potential_c["route_contribution"] == 0.4
    assert potential_c["potential_contribution"] == 0.25


def test_manual_evidence_migration_leaves_unknown_banked_total_null():
    with database.connect() as conn:
        cursor = conn.cursor()

        # Simulate a database created before
        # banked_total_at_submission existed.
        cursor.execute(
            '''
            ALTER TABLE manual_evidence
            DROP COLUMN banked_total_at_submission
            '''
        )

        cursor.execute(
            '''
            INSERT INTO manual_evidence (
                evidence_path,
                evidence_sha256,
                submission_source,
                submitter_id,
                submitter_name
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING evidence_id
            ''',
            (
                "manual/historical-evidence.png",
                "e" * 64,
                "DISCORD",
                12345,
                "Historical Staff"
            )
        )

        evidence_id = cursor.fetchone()[0]

        conn.commit()

    # Run the real migration path.
    database.ensure_schema()

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT banked_total_at_submission
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (evidence_id,)
        )

        migrated_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'manual_evidence'
              AND column_name = 'banked_total_at_submission'
            '''
        )

        column = cursor.fetchone()

    assert migrated_row is not None
    assert migrated_row[0] is None

    assert column is not None
    assert column[0] == "numeric"
    assert column[1] == "YES"


def test_manual_evidence_refuses_completed_tile():
    create_test_player(
        "Manual Completed Tile Tester",
        team_name="Manual Completed Tile Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Completed Tile Test",
        tile_points=2,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Completed Tile Drop",
                "target": 1
            }
        ]
    )

    player = database.get_player_by_name(
        "Manual Completed Tile Tester"
    )

    assert player is not None

    condition_id = database.get_tile_conditions(
        tile_id
    )[0][0]

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO completed_tiles (
                tile_id,
                team_id
            )
            VALUES (%s, %s)
            ''',
            (
                tile_id,
                player[5]
            )
        )
        conn.commit()

    with pytest.raises(
        ValueError,
        match="this tile is already complete"
    ):
        database.add_manual_evidence(
            player_id=player[0],
            condition_id=condition_id,
            amount=1,
            evidence_path="manual/completed-tile.png",
            evidence_sha256="e" * 64,
            submission_source="DISCORD",
            submitter_id=12345,
            submitter_name="Test Staff"
        )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM manual_evidence
            WHERE player_id = %s
              AND tile_id = %s
            ''',
            (
                player[0],
                tile_id
            )
        )

        assert cursor.fetchone()[0] == 0


def test_manual_evidence_refuses_completed_all_condition():
    create_test_player(
        "Manual ALL Tester",
        team_name="Manual ALL Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual ALL Eligibility Test",
        tile_points=2,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "ALL Completed Drop",
                "target": 2
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "ALL Incomplete Drop",
                "target": 3
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    player = database.get_player_by_name(
        "Manual ALL Tester"
    )

    assert player is not None

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
              AND condition_trigger = %s
            ''',
            (
                tile_id,
                "ALL Completed Drop"
            )
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
                player[5],
                condition_id,
                2
            )
        )

        conn.commit()

    with pytest.raises(
        ValueError,
        match="this part of the tile is already complete"
    ):
        database.add_manual_evidence(
            player_id=player[0],
            condition_id=condition_id,
            amount=1,
            evidence_path="manual/all-complete.png",
            evidence_sha256="f" * 64,
            submission_source="DISCORD",
            submitter_id=12345,
            submitter_name="Test Staff"
        )


def test_manual_evidence_sum_allows_repeated_condition_until_route_complete():
    create_test_player(
        "Manual SUM Tester",
        team_name="Manual SUM Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual SUM Eligibility Test",
        tile_points=3,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "SUM Repeated Drop",
                "target": 2
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "SUM Other Drop",
                "target": 2
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

    player = database.get_player_by_name(
        "Manual SUM Tester"
    )

    assert player is not None

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
              AND condition_trigger = %s
            ''',
            (
                tile_id,
                "SUM Repeated Drop"
            )
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
                player[5],
                condition_id,
                3
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=2,
        evidence_path="manual/sum-repeat.png",
        evidence_sha256="1" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Test Staff"
    )

    assert submission["status"] == "PENDING"

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            UPDATE tile_condition_progress
            SET progress = %s
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                10,
                player[5],
                condition_id
            )
        )

        conn.commit()

    with pytest.raises(
        ValueError,
        match="this completion route is already complete"
    ):
        database.add_manual_evidence(
            player_id=player[0],
            condition_id=condition_id,
            amount=1,
            evidence_path="manual/sum-complete.png",
            evidence_sha256="2" * 64,
            submission_source="DISCORD",
            submitter_id=12345,
            submitter_name="Test Staff"
        )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM manual_evidence
            WHERE player_id = %s
              AND tile_id = %s
            ''',
            (
                player[0],
                tile_id
            )
        )

        assert cursor.fetchone()[0] == 1


def test_manual_evidence_refuses_used_unique_n_of_condition():
    create_test_player(
        "Manual Unique N Of Tester",
        team_name="Manual Unique N Of Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Unique N Of Eligibility Test",
        tile_points=3,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Unique Evidence A",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Unique Evidence B",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Unique Evidence C",
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

    player = database.get_player_by_name(
        "Manual Unique N Of Tester"
    )

    assert player is not None

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT condition_id
            FROM tile_conditions
            WHERE tile_id = %s
              AND condition_trigger = %s
            ''',
            (
                tile_id,
                "Unique Evidence A"
            )
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
                player[5],
                condition_id,
                1
            )
        )

        conn.commit()

    with pytest.raises(
        ValueError,
        match="this unique part of the tile has already contributed"
    ):
        database.add_manual_evidence(
            player_id=player[0],
            condition_id=condition_id,
            amount=1,
            evidence_path="manual/unique-used.png",
            evidence_sha256="3" * 64,
            submission_source="DISCORD",
            submitter_id=12345,
            submitter_name="Test Staff"
        )


def test_manual_evidence_non_unique_n_of_allows_repeats_until_route_complete():
    create_test_player(
        "Manual Repeat N Of Tester",
        team_name="Manual Repeat N Of Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Repeat N Of Eligibility Test",
        tile_points=3,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 5,
                "require_unique": False
            }
        ]
    )

    player = database.get_player_by_name(
        "Manual Repeat N Of Tester"
    )

    assert player is not None

    condition_id = database.get_tile_conditions(
        tile_id
    )[0][0]

    with database.connect() as conn:
        cursor = conn.cursor()

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
                player[5],
                condition_id,
                2
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=2,
        evidence_path="manual/non-unique-repeat.png",
        evidence_sha256="4" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Test Staff"
    )

    assert submission["status"] == "PENDING"

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            UPDATE tile_condition_progress
            SET progress = %s
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                5,
                player[5],
                condition_id
            )
        )

        conn.commit()

    with pytest.raises(
        ValueError,
        match="this completion route is already complete"
    ):
        database.add_manual_evidence(
            player_id=player[0],
            condition_id=condition_id,
            amount=1,
            evidence_path="manual/non-unique-complete.png",
            evidence_sha256="5" * 64,
            submission_source="DISCORD",
            submitter_id=12345,
            submitter_name="Test Staff"
        )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM manual_evidence
            WHERE player_id = %s
              AND tile_id = %s
            ''',
            (
                player[0],
                tile_id
            )
        )

        assert cursor.fetchone()[0] == 1


def test_manual_evidence_warns_about_earlier_pending_tile_submission():
    create_test_player(
        "Manual Pending Warning Tester",
        team_name="Manual Pending Warning Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Pending Warning Test",
        tile_points=3,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Pending Warning Drop A",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Pending Warning Drop B",
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

    player = database.get_player_by_name(
        "Manual Pending Warning Tester"
    )

    assert player is not None

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                condition_id,
                condition_trigger
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_ids = {
            trigger: condition_id
            for condition_id, trigger in cursor.fetchall()
        }

    first_submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_ids[
            "Pending Warning Drop A"
        ],
        amount=1,
        evidence_path="manual/pending-warning-a.png",
        evidence_sha256="6" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Test Staff"
    )

    assert (
        first_submission["has_earlier_pending_evidence"]
        is False
    )
    assert (
        first_submission["earlier_pending_evidence_count"]
        == 0
    )
    assert first_submission["pending_warning"] is None

    second_submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_ids[
            "Pending Warning Drop B"
        ],
        amount=1,
        evidence_path="manual/pending-warning-b.png",
        evidence_sha256="7" * 64,
        submission_source="DISCORD",
        submitter_id=67890,
        submitter_name="Other Test Staff"
    )

    assert (
        second_submission["has_earlier_pending_evidence"]
        is True
    )
    assert (
        second_submission["earlier_pending_evidence_count"]
        == 1
    )
    assert second_submission["pending_warning"] == (
        "Another submission for this tile is already "
        "waiting for review. If that earlier submission "
        "is accepted, it may reduce or remove the MVP "
        "points available for this submission. This will "
        "not affect the team's tile points."
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM manual_evidence
            WHERE team_id = %s
              AND tile_id = %s
              AND status = 'PENDING'
            ''',
            (
                player[5],
                tile_id
            )
        )

        assert cursor.fetchone()[0] == 2


def test_manual_evidence_review_requires_oldest_pending_first():
    create_test_player(
        "Manual Review Order Tester",
        team_name="Manual Review Order Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Review Order Test",
        tile_points=3,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Review Order Drop A",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Review Order Drop B",
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

    player = database.get_player_by_name(
        "Manual Review Order Tester"
    )

    assert player is not None

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                condition_id,
                condition_trigger
            FROM tile_conditions
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        condition_ids = {
            trigger: condition_id
            for condition_id, trigger in cursor.fetchall()
        }

    first_submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_ids[
            "Review Order Drop A"
        ],
        amount=1,
        evidence_path="manual/review-order-a.png",
        evidence_sha256="8" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="First Submitter"
    )

    second_submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_ids[
            "Review Order Drop B"
        ],
        amount=1,
        evidence_path="manual/review-order-b.png",
        evidence_sha256="9" * 64,
        submission_source="DISCORD",
        submitter_id=67890,
        submitter_name="Second Submitter"
    )

    blocked_result = database.reject_pending_manual_evidence(
        evidence_id=second_submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=11111,
        reviewer_name="Reviewing Staff",
        reason="Second submission test rejection."
    )

    assert blocked_result == {
        "status": "EARLIER_PENDING_EVIDENCE",
        "earlier_evidence_id":
            first_submission["evidence_id"],
        "message": (
            "An earlier submission for this tile is "
            "still waiting for review. Review that "
            "submission first."
        )
    }

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (second_submission["evidence_id"],)
        )

        assert cursor.fetchone()[0] == "PENDING"

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM staff_review_decisions
            WHERE subject_type = 'MANUAL_EVIDENCE'
              AND subject_id = %s
            ''',
            (second_submission["evidence_id"],)
        )

        assert cursor.fetchone()[0] == 0

    first_result = database.reject_pending_manual_evidence(
        evidence_id=first_submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=11111,
        reviewer_name="Reviewing Staff",
        reason="First submission test rejection."
    )

    assert first_result["status"] == "REJECTED"

    second_result = database.reject_pending_manual_evidence(
        evidence_id=second_submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=11111,
        reviewer_name="Reviewing Staff",
        reason="Second submission test rejection."
    )

    assert second_result["status"] == "REJECTED"

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                evidence_id,
                status
            FROM manual_evidence
            WHERE evidence_id IN (%s, %s)
            ORDER BY evidence_id
            ''',
            (
                first_submission["evidence_id"],
                second_submission["evidence_id"]
            )
        )

        assert cursor.fetchall() == [
            (
                first_submission["evidence_id"],
                "REJECTED"
            ),
            (
                second_submission["evidence_id"],
                "REJECTED"
            )
        ]


def test_accept_pending_manual_evidence_records_incomplete_progress():
    create_test_player(
        "Manual Acceptance Tester",
        team_name="Manual Acceptance Team"
    )

    player = database.get_player_by_name(
        "Manual Acceptance Tester"
    )

    assert player is not None

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Acceptance Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Acceptance Drop",
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

        # The team has already made 20% route progress, but no
        # personal contribution has yet been banked for it.
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
                player[5],
                condition_id,
                2
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=3,
        evidence_path="manual/acceptance-test.png",
        evidence_sha256="f" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert result["status"] == "ACCEPTED"
    assert result["evidence_id"] == submission["evidence_id"]
    assert result["player_id"] == player[0]
    assert result["team_id"] == player[5]
    assert result["tile_id"] == tile_id
    assert result["condition_id"] == condition_id
    assert result["completion_path"] == 1
    assert result["amount"] == 3

    assert result["raw_progress"] == 5
    assert result["route_progress"] == 0.5
    assert result["route_progress_delta"] == 0.3

    assert result["actual_contribution"] == 0.3
    assert result["completion_remainder"] == 0.0
    assert result["normal_player_credit"] == 0.3
    assert result["potential_contribution"] == 0.3
    assert result["lost_mvp_contribution"] == 0.0
    assert result["banked_total"] == 0.3

    assert result["ready"] is False
    assert result["completed"] is False
    assert result["player_deleted"] is False

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        evidence_status = cursor.fetchone()[0]

        cursor.execute(
            '''
            SELECT
                progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                player[5],
                condition_id
            )
        )

        live_progress = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT
                partial_completion
            FROM partial_completions
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ''',
            (
                player[0],
                player[5],
                tile_id
            )
        )

        partial_completion = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT
                amount,
                raw_progress,
                route_progress,
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution,
                banked_total,
                ready,
                completed
            FROM manual_evidence_progress
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        progress_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                decision,
                review_source,
                reviewer_id,
                reviewer_name
            FROM staff_review_decisions
            WHERE subject_type = 'MANUAL_EVIDENCE'
              AND subject_id = %s
            ''',
            (submission["evidence_id"],)
        )

        decision = cursor.fetchone()

        cursor.execute(
            '''
            SELECT 1
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                player[5],
                tile_id
            )
        )

        completed_tile = cursor.fetchone()

    assert evidence_status == "ACCEPTED"
    assert live_progress == 5
    assert partial_completion == 0.3

    assert progress_row[0] == 3
    assert progress_row[1] == 5

    assert float(progress_row[2]) == 0.5
    assert float(progress_row[3]) == 0.3
    assert float(progress_row[4]) == 0.0
    assert float(progress_row[5]) == 0.3
    assert float(progress_row[6]) == 0.3
    assert float(progress_row[7]) == 0.0
    assert float(progress_row[8]) == 0.3

    assert progress_row[9] is False
    assert progress_row[10] is False

    assert decision == (
        "ACCEPT",
        "DISCORD",
        54321,
        "Reviewing Staff"
    )

    assert completed_tile is None


def test_accept_pending_manual_evidence_completes_tile_with_remainder():
    create_test_player(
        "Manual Completion Tester",
        team_name="Manual Completion Team"
    )

    player = database.get_player_by_name(
        "Manual Completion Tester"
    )

    assert player is not None

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Completion Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Completion Drop",
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

        # The route is already 60% complete, while only 20% of
        # the tile's personal contribution has been banked.
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
                player[5],
                condition_id,
                6
            )
        )

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
                player[0],
                player[5],
                tile_id,
                0.2
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/completion-test.png",
        evidence_sha256="9" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["banked_total_at_submission"] == 0.2

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert result["status"] == "ACCEPTED"
    assert result["raw_progress"] == 10
    assert result["route_progress"] == 1.0
    assert result["route_progress_delta"] == 0.4

    assert result["actual_contribution"] == 0.4
    assert result["completion_remainder"] == 0.4
    assert result["normal_player_credit"] == 0.8

    assert result["potential_contribution"] == 0.4
    assert result["lost_mvp_contribution"] == 0.0

    # This is the total immediately after the evidence's normal
    # 40% contribution is banked, before the completion helper
    # allocates the remaining 40% finisher remainder.
    assert result["banked_total"] == 0.6

    assert result["ready"] is True
    assert result["completed"] is True
    assert result["player_deleted"] is False

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                amount,
                raw_progress,
                route_progress,
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution,
                banked_total,
                ready,
                completed
            FROM manual_evidence_progress
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        progress_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                contribution,
                points_awarded,
                credit_type,
                evidence_id
            FROM player_tile_credits
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ORDER BY credit_id
            ''',
            (
                player[0],
                player[5],
                tile_id
            )
        )

        credits = cursor.fetchall()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                player[5],
                tile_id
            )
        )

        completed_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM partial_completions
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                player[5],
                tile_id
            )
        )

        partial_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        evidence_status = cursor.fetchone()[0]

    assert progress_row[0] == 4
    assert progress_row[1] == 10
    assert float(progress_row[2]) == 1.0
    assert float(progress_row[3]) == 0.4
    assert float(progress_row[4]) == 0.4
    assert float(progress_row[5]) == 0.8
    assert float(progress_row[6]) == 0.4
    assert float(progress_row[7]) == 0.0
    assert float(progress_row[8]) == 0.6
    assert progress_row[9] is True
    assert progress_row[10] is True

    assert len(credits) == 1

    credit = credits[0]

    assert float(credit[0]) == 1.0
    assert float(credit[1]) == 4.0
    assert credit[2] == "TILE_COMPLETION"
    assert credit[3] is None

    assert team_points == 4.0
    assert completed_count == 1
    assert partial_count == 0
    assert evidence_status == "ACCEPTED"


def test_late_manual_evidence_accepts_without_discretionary_mvp_by_default():
    create_test_player(
        "Late Evidence Tester",
        team_name="Late Evidence Team"
    )

    create_test_player(
        "Late Evidence Finisher",
        team_name="Late Evidence Team"
    )

    player = database.get_player_by_name(
        "Late Evidence Tester"
    )

    finisher = database.get_player_by_name(
        "Late Evidence Finisher"
    )

    assert player is not None
    assert finisher is not None
    assert player[5] == finisher[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Late Evidence Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Late Evidence Drop",
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

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/late-evidence-test.png",
        evidence_sha256="a" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["banked_total_at_submission"] == 0.0

    # The evidence already exists when another source completes
    # the live tile.
    with database.connect() as conn:
        cursor = conn.cursor()

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
                player[5],
                condition_id,
                10
            )
        )

        completion_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=player[5],
                tile_id=tile_id,
                finisher_player_id=finisher[0],
                return_details=True
            )
        )

        assert completion_result["completed"] is True

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points_before_review = float(
            cursor.fetchone()[0]
        )

        conn.commit()

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert result["status"] == "ACCEPTED"
    assert result["late_review"] is True
    assert result["submitted_before_completion"] is True

    assert result["actual_contribution"] == 0.0
    assert result["completion_remainder"] == 0.0
    assert result["normal_player_credit"] == 0.0

    assert result["potential_contribution"] == 0.4
    assert result["lost_mvp_contribution"] == 0.4

    assert result["award_lost_mvp_requested"] is False
    assert result["existing_personal_credit"] == 0.0
    assert result["remaining_personal_credit"] == 1.0
    assert result["late_review_contribution"] == 0.0
    assert result["late_review_points"] == 0.0

    assert result["ready"] is True
    assert result["completed"] is True
    assert result["player_deleted"] is False

    player_evidence = database.get_player_bingo_evidence(
        player[0]
    )

    evidence_row = next(
        row
        for row in player_evidence
        if (
            row["evidence_type"] == "manual"
            and row["evidence_id"] == submission["evidence_id"]
        )
    )

    assert evidence_row["contribution"] == 0.0
    assert evidence_row["status"] == "Accepted — progress recorded"

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        evidence_status = cursor.fetchone()[0]

        cursor.execute(
            '''
            SELECT
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution,
                banked_total,
                ready,
                completed
            FROM manual_evidence_progress
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        progress_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        player_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        late_review_credit_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points_after_review = float(
            cursor.fetchone()[0]
        )

    assert evidence_status == "ACCEPTED"

    assert float(progress_row[0]) == 0.0
    assert float(progress_row[1]) == 0.0
    assert float(progress_row[2]) == 0.0
    assert float(progress_row[3]) == 0.4
    assert float(progress_row[4]) == 0.4
    assert float(progress_row[5]) == 1.0
    assert progress_row[6] is True
    assert progress_row[7] is True

    assert float(player_row[0]) == 0.0
    assert float(player_row[1]) == 0.0

    assert late_review_credit_count == 0

    # Accepting the late evidence must not award the team the
    # tile a second time.
    assert team_points_after_review == team_points_before_review
    assert team_points_after_review == 4.0


def test_late_manual_evidence_awards_discretionary_mvp_when_requested():
    create_test_player(
        "Late MVP Tester",
        team_name="Late MVP Team"
    )

    create_test_player(
        "Late MVP Finisher",
        team_name="Late MVP Team"
    )

    player = database.get_player_by_name(
        "Late MVP Tester"
    )

    finisher = database.get_player_by_name(
        "Late MVP Finisher"
    )

    assert player is not None
    assert finisher is not None
    assert player[5] == finisher[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Late MVP Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Late MVP Drop",
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

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/late-mvp-test.png",
        evidence_sha256="b" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["banked_total_at_submission"] == 0.0

    # The tile was worth four points when this evidence was
    # submitted. Changing only the point value is deliberately
    # compatible, but any late-review award must still use the
    # frozen four-point value.
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            UPDATE tiles
            SET tile_points = %s
            WHERE tile_id = %s
            ''',
            (
                9,
                tile_id
            )
        )

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
                player[5],
                condition_id,
                10
            )
        )

        completion_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=player[5],
                tile_id=tile_id,
                finisher_player_id=finisher[0],
                return_details=True
            )
        )

        assert completion_result["completed"] is True
        assert completion_result["tile_points"] == 9.0

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points_before_review = float(
            cursor.fetchone()[0]
        )

        conn.commit()

    preflight = (
        database.get_manual_evidence_lost_mvp_preflight(
            submission["evidence_id"]
        )
    )

    assert preflight["status"] == "READY"
    assert preflight["lost_mvp_available"] is True
    assert preflight["tile_already_completed"] is True
    assert preflight["would_complete_tile"] is False

    assert preflight["potential_contribution"] == 0.4
    assert preflight["predicted_actual_contribution"] == 0.0
    assert preflight["lost_mvp_contribution"] == 0.4

    assert preflight["existing_personal_credit"] == 0.0
    assert preflight["remaining_personal_credit"] == 1.0

    assert (
        preflight["maximum_lost_mvp_contribution"]
        == 0.4
    )

    # The prompt must use the frozen four-point tile value,
    # not the live nine-point value.
    assert preflight["maximum_lost_mvp_points"] == 1.6

    # Preflight is strictly read-only. It must not review the
    # evidence or award any progress/MVP itself.
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        assert cursor.fetchone()[0] == "PENDING"

        cursor.execute(
            '''
            SELECT player_points
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        assert float(cursor.fetchone()[0]) == 0.0

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM manual_evidence_progress
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        assert int(cursor.fetchone()[0]) == 0

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        assert int(cursor.fetchone()[0]) == 0

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff",
        award_lost_mvp=True
    )

    assert result["status"] == "ACCEPTED"
    assert result["late_review"] is True
    assert result["submitted_before_completion"] is True

    assert result["actual_contribution"] == 0.0
    assert result["completion_remainder"] == 0.0
    assert result["normal_player_credit"] == 0.0

    assert result["potential_contribution"] == 0.4
    assert result["lost_mvp_contribution"] == 0.4

    assert result["award_lost_mvp_requested"] is True
    assert result["existing_personal_credit"] == 0.0
    assert result["remaining_personal_credit"] == 1.0

    assert result["late_review_contribution"] == 0.4

    # 40% of the frozen four-point tile value, not the current
    # nine-point value.
    assert result["late_review_points"] == 1.6

    assert result["player_deleted"] is False

    player_evidence = database.get_player_bingo_evidence(
        player[0]
    )

    evidence_row = next(
        row
        for row in player_evidence
        if (
            row["evidence_type"] == "manual"
            and row["evidence_id"] == submission["evidence_id"]
        )
    )

    assert evidence_row["contribution"] == 0.0
    assert evidence_row["status"] == "Accepted — MVP awarded"

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        player_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                contribution,
                points_awarded,
                credit_type,
                evidence_id,
                team_id,
                tile_id
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        credit_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                actual_contribution,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution
            FROM manual_evidence_progress
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        progress_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points_after_review = float(
            cursor.fetchone()[0]
        )

    assert float(player_row[0]) == 1.6

    # Late review awards MVP only. It is not another tile
    # completion for the player.
    assert float(player_row[1]) == 0.0

    assert credit_row is not None
    assert float(credit_row[0]) == 0.4
    assert float(credit_row[1]) == 1.6
    assert credit_row[2] == "LATE_REVIEW"
    assert credit_row[3] == submission["evidence_id"]
    assert credit_row[4] == player[5]
    assert credit_row[5] == tile_id

    assert float(progress_row[0]) == 0.0
    assert float(progress_row[1]) == 0.0
    assert float(progress_row[2]) == 0.4
    assert float(progress_row[3]) == 0.4

    # The live tile was worth nine points when it completed.
    # Reviewing the evidence afterwards must not alter the team's
    # score.
    assert team_points_before_review == 9.0
    assert team_points_after_review == 9.0


def test_late_manual_evidence_discretionary_mvp_respects_personal_cap():
    create_test_player(
        "Late Cap Tester",
        team_name="Late Cap Team"
    )

    create_test_player(
        "Late Cap Finisher",
        team_name="Late Cap Team"
    )

    player = database.get_player_by_name(
        "Late Cap Tester"
    )

    finisher = database.get_player_by_name(
        "Late Cap Finisher"
    )

    assert player is not None
    assert finisher is not None
    assert player[5] == finisher[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Late Cap Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Late Cap Drop",
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

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/late-cap-test.png",
        evidence_sha256="c" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    # There was no personal/team contribution banked when this
    # evidence was submitted, so its frozen potential is 40%.
    assert submission["banked_total_at_submission"] == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        # After submission, this player earns 80% of the tile
        # through another source. This will become normal personal
        # credit when the tile completes.
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
                player[0],
                player[5],
                tile_id,
                0.8
            )
        )

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
                player[5],
                condition_id,
                10
            )
        )

        completion_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=player[5],
                tile_id=tile_id,
                finisher_player_id=finisher[0],
                return_details=True
            )
        )

        assert completion_result["completed"] is True

        conn.commit()

    preflight = (
        database.get_manual_evidence_lost_mvp_preflight(
            submission["evidence_id"]
        )
    )

    assert preflight["status"] == "READY"
    assert preflight["lost_mvp_available"] is True
    assert preflight["tile_already_completed"] is True
    assert preflight["would_complete_tile"] is False

    # The frozen evidence originally had 40% potential, but the
    # player already owns 80% personal credit for this team/tile.
    assert preflight["potential_contribution"] == 0.4
    assert preflight["predicted_actual_contribution"] == 0.0
    assert preflight["lost_mvp_contribution"] == 0.4

    assert preflight["existing_personal_credit"] == 0.8
    assert preflight["remaining_personal_credit"] == 0.2

    # The organiser must only be offered the remaining 20%, not
    # the full 40% that was lost when the tile completed.
    assert (
        preflight["maximum_lost_mvp_contribution"]
        == 0.2
    )

    # 20% of the frozen four-point tile.
    assert preflight["maximum_lost_mvp_points"] == 0.8

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff",
        award_lost_mvp=True
    )

    assert result["status"] == "ACCEPTED"
    assert result["late_review"] is True

    # The frozen evidence could originally have contributed 40%.
    assert result["potential_contribution"] == 0.4
    assert result["lost_mvp_contribution"] == 0.4

    # By review time the player already owns 80% normal credit
    # for this team/tile, so only another 20% may be awarded.
    assert result["existing_personal_credit"] == 0.8
    assert result["remaining_personal_credit"] == 0.2

    assert result["award_lost_mvp_requested"] is True
    assert result["late_review_contribution"] == 0.2

    # 20% of the frozen four-point tile.
    assert result["late_review_points"] == 0.8

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                contribution,
                points_awarded
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        late_credit = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                COALESCE(SUM(contribution), 0)
            FROM player_tile_credits
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ''',
            (
                player[0],
                player[5],
                tile_id
            )
        )

        total_personal_credit = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT
                player_points
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        player_points = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points = float(
            cursor.fetchone()[0]
        )

    assert late_credit is not None
    assert float(late_credit[0]) == 0.2
    assert float(late_credit[1]) == 0.8

    # 80% normal credit + 20% discretionary credit = exactly
    # the 100% cap for this player/team/tile.
    assert total_personal_credit == 1.0

    # 80% of four points from normal completion plus another
    # 20% from late review = the full four personal points.
    assert player_points == 4.0

    # Late review never changes the team's tile score.
    assert team_points == 4.0


def test_manual_evidence_keeps_full_mvp_when_tile_remains_incomplete():
    create_test_player(
        "Queued Evidence Tester",
        team_name="Queued Evidence Team"
    )

    player = database.get_player_by_name(
        "Queued Evidence Tester"
    )

    assert player is not None

    tile_id = database.add_tile_with_conditions(
        tile_name="Queued Evidence Progress Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Queued Evidence Drop",
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

        # The tile is at 10% when the evidence is submitted.
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
                player[5],
                condition_id,
                1
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=5,
        evidence_path="manual/queued-progress-test.png",
        evidence_sha256="d" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    # The evidence could contribute a full 50% when submitted.
    assert submission["banked_total_at_submission"] == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        # Automation adds another 20% while the submission waits
        # for review, moving the live tile from 10% to 30%.
        cursor.execute(
            '''
            UPDATE tile_condition_progress
            SET progress = %s
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                3,
                player[5],
                condition_id
            )
        )

        conn.commit()

    preflight = (
        database.get_manual_evidence_lost_mvp_preflight(
            submission["evidence_id"]
        )
    )

    assert preflight["status"] == "READY"
    assert preflight["lost_mvp_available"] is False
    assert preflight["tile_already_completed"] is False
    assert preflight["would_complete_tile"] is False

    # The queued evidence can still receive its complete 50%
    # contribution, so there is no discretionary MVP decision.
    assert preflight["potential_contribution"] == 0.5
    assert preflight["route_progress_delta"] == 0.5
    assert preflight["predicted_actual_contribution"] == 0.5
    assert preflight["lost_mvp_contribution"] == 0.0

    assert preflight["existing_personal_credit"] == 0.0
    assert preflight["predicted_personal_credit"] == 0.5
    assert preflight["remaining_personal_credit"] == 0.5

    assert (
        preflight["maximum_lost_mvp_contribution"]
        == 0.0
    )
    assert preflight["maximum_lost_mvp_points"] == 0.0

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert result["status"] == "ACCEPTED"

    # The queued evidence still contributes its full 50%.
    assert result["potential_contribution"] == 0.5
    assert result["actual_contribution"] == 0.5
    assert result["normal_player_credit"] == 0.5

    # 30% live progress + 50% evidence = 80%, so the tile remains
    # incomplete and none of the queued evidence has been lost.
    assert result["raw_progress"] == 8
    assert result["route_progress"] == 0.8
    assert result["route_progress_delta"] == 0.5
    assert result["ready"] is False
    assert result["completed"] is False
    assert result["lost_mvp_contribution"] == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                partial_completion
            FROM partial_completions
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ''',
            (
                player[0],
                player[5],
                tile_id
            )
        )

        partial_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        late_review_credit_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points = float(
            cursor.fetchone()[0]
        )

    assert partial_row is not None

    # The complete 50% has been banked as this player's normal
    # contribution and will be converted into MVP points when the
    # tile eventually completes.
    assert float(partial_row[0]) == 0.5

    # No discretionary compensation exists because nothing was
    # truncated by tile completion.
    assert late_review_credit_count == 0

    # The tile is not complete yet.
    assert team_points == 0.0


def test_manual_evidence_completion_can_award_truncated_lost_mvp():
    create_test_player(
        "Truncated Evidence Tester",
        team_name="Truncated Evidence Team"
    )

    create_test_player(
        "Truncated Automation Player",
        team_name="Truncated Evidence Team"
    )

    player = database.get_player_by_name(
        "Truncated Evidence Tester"
    )

    automation_player = database.get_player_by_name(
        "Truncated Automation Player"
    )

    assert player is not None
    assert automation_player is not None
    assert player[5] == automation_player[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Truncated Evidence Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Truncated Evidence Drop",
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

        # The tile is at 10% when Player A submits their evidence.
        # That existing 10% already belongs to another player.
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
                player[5],
                condition_id,
                1
            )
        )

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
                automation_player[0],
                player[5],
                tile_id,
                0.1
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=5,
        evidence_path="manual/truncated-evidence-test.png",
        evidence_sha256="e" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    # At submission the tile is 10% complete and Player A's
    # evidence could contribute its full 50%.
    assert submission["banked_total_at_submission"] == 0.1

    with database.connect() as conn:
        cursor = conn.cursor()

        # Automation subsequently adds another 70%, taking the
        # live tile from 10% to 80% before staff reviews Player A's
        # queued evidence.
        cursor.execute(
            '''
            UPDATE tile_condition_progress
            SET progress = %s
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                8,
                player[5],
                condition_id
            )
        )

        cursor.execute(
            '''
            UPDATE partial_completions
            SET partial_completion = %s
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ''',
            (
                0.8,
                automation_player[0],
                player[5],
                tile_id
            )
        )

        conn.commit()

    preflight = (
        database.get_manual_evidence_lost_mvp_preflight(
            submission["evidence_id"]
        )
    )

    assert preflight["status"] == "READY"
    assert preflight["lost_mvp_available"] is True
    assert preflight["tile_already_completed"] is False
    assert preflight["would_complete_tile"] is True

    # Player A originally had 50% potential, but only 20% of
    # the live tile remains available when staff reviews it.
    assert preflight["potential_contribution"] == 0.5
    assert preflight["route_progress_delta"] == 0.2
    assert preflight["predicted_actual_contribution"] == 0.2

    # The other player's existing 80% plus Player A's predicted
    # 20% accounts for the whole tile, so no finisher remainder
    # would be added.
    assert preflight["completion_remainder"] == 0.0

    assert preflight["existing_personal_credit"] == 0.0
    assert preflight["predicted_personal_credit"] == 0.2
    assert preflight["remaining_personal_credit"] == 0.8

    # Completion would truncate the remaining 30% of Player A's
    # otherwise-valid queued contribution.
    assert preflight["lost_mvp_contribution"] == 0.3
    assert (
        preflight["maximum_lost_mvp_contribution"]
        == 0.3
    )

    # 30% of the frozen four-point tile.
    assert preflight["maximum_lost_mvp_points"] == 1.2

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff",
        award_lost_mvp=True
    )

    assert result["status"] == "ACCEPTED"

    # Player A originally had 50% potential, but only the final
    # 20% of the live tile remains available at review time.
    assert result["potential_contribution"] == 0.5
    assert result["actual_contribution"] == 0.2

    assert result["route_progress"] == 1.0
    assert result["route_progress_delta"] == 0.2
    assert result["ready"] is True
    assert result["completed"] is True

    # The other player's 80% plus Player A's actual 20% already
    # accounts for the whole tile, so there is no completion
    # remainder to give Player A.
    assert result["completion_remainder"] == 0.0
    assert result["normal_player_credit"] == 0.2

    # Completion has truncated 30% of Player A's otherwise valid
    # queued evidence.
    assert result["lost_mvp_contribution"] == 0.3

    # Staff explicitly chose to award that lost 30%.
    assert result["award_lost_mvp_requested"] is True
    assert result["late_review_contribution"] == 0.3

    # 30% of the four-point tile.
    assert result["late_review_points"] == 1.2

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                contribution,
                points_awarded,
                credit_type,
                evidence_id
            FROM player_tile_credits
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ORDER BY credit_type
            ''',
            (
                player[0],
                player[5],
                tile_id
            )
        )

        credits = cursor.fetchall()

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        player_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points = float(
            cursor.fetchone()[0]
        )

    assert len(credits) == 2

    credit_by_type = {
        credit[2]: credit
        for credit in credits
    }

    normal_credit = credit_by_type["TILE_COMPLETION"]
    late_credit = credit_by_type["LATE_REVIEW"]

    assert float(normal_credit[0]) == 0.2
    assert float(normal_credit[1]) == 0.8
    assert normal_credit[3] is None

    assert float(late_credit[0]) == 0.3
    assert float(late_credit[1]) == 1.2
    assert late_credit[3] == submission["evidence_id"]

    # Player A receives 20% normal credit plus the discretionary
    # 30% lost-MVP award: 50% of a four-point tile in total.
    assert float(player_row[0]) == 2.0

    # Discretionary compensation does not count as additional
    # tile completion credit.
    assert float(player_row[1]) == 0.2

    # The team still receives the tile's normal four points once.
    assert team_points == 4.0


def test_manual_evidence_completion_does_not_award_lost_mvp_by_default():
    create_test_player(
        "Truncated Default Tester",
        team_name="Truncated Default Team"
    )

    create_test_player(
        "Truncated Default Automation Player",
        team_name="Truncated Default Team"
    )

    player = database.get_player_by_name(
        "Truncated Default Tester"
    )

    automation_player = database.get_player_by_name(
        "Truncated Default Automation Player"
    )

    assert player is not None
    assert automation_player is not None
    assert player[5] == automation_player[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Truncated Default Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Truncated Default Drop",
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

        # The tile is at 10% when the manual evidence is submitted.
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
                player[5],
                condition_id,
                1
            )
        )

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
                automation_player[0],
                player[5],
                tile_id,
                0.1
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=5,
        evidence_path="manual/truncated-default-test.png",
        evidence_sha256="f" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["banked_total_at_submission"] == 0.1

    with database.connect() as conn:
        cursor = conn.cursor()

        # Automation then takes the tile to 80%, leaving only 20%
        # available for the queued 50% manual submission.
        cursor.execute(
            '''
            UPDATE tile_condition_progress
            SET progress = %s
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                8,
                player[5],
                condition_id
            )
        )

        cursor.execute(
            '''
            UPDATE partial_completions
            SET partial_completion = %s
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ''',
            (
                0.8,
                automation_player[0],
                player[5],
                tile_id
            )
        )

        conn.commit()

    # award_lost_mvp is deliberately omitted. The default must be
    # False so discretionary compensation can never happen
    # automatically.
    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert result["status"] == "ACCEPTED"
    assert result["completed"] is True

    assert result["potential_contribution"] == 0.5
    assert result["actual_contribution"] == 0.2
    assert result["normal_player_credit"] == 0.2

    # The final 30% of the otherwise-valid submission has been
    # truncated by tile completion.
    assert result["lost_mvp_contribution"] == 0.3

    # The bingo bot reports that compensation was available, but staff
    # did not explicitly request it.
    assert result["award_lost_mvp_requested"] is False
    assert result["late_review_contribution"] == 0.0
    assert result["late_review_points"] == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                contribution,
                points_awarded,
                credit_type,
                evidence_id
            FROM player_tile_credits
            WHERE player_id = %s
              AND team_id = %s
              AND tile_id = %s
            ORDER BY credit_type
            ''',
            (
                player[0],
                player[5],
                tile_id
            )
        )

        credits = cursor.fetchall()

        cursor.execute(
            '''
            SELECT
                player_points,
                tiles_completed
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        player_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (player[5],)
        )

        team_points = float(
            cursor.fetchone()[0]
        )

    # Player A receives only their normal 20% credit.
    assert len(credits) == 1

    normal_credit = credits[0]

    assert float(normal_credit[0]) == 0.2
    assert float(normal_credit[1]) == 0.8
    assert normal_credit[2] == "TILE_COMPLETION"
    assert normal_credit[3] is None

    assert float(player_row[0]) == 0.8
    assert float(player_row[1]) == 0.2

    # No LATE_REVIEW ledger row exists because the staff member
    # left the discretionary option unticked.
    assert all(
        credit[2] != "LATE_REVIEW"
        for credit in credits
    )

    assert team_points == 4.0


def test_manual_evidence_stays_with_original_team_after_player_moves():
    create_test_player(
        "Manual Moved Player",
        team_name="Manual Original Team"
    )

    create_test_player(
        "Manual New Team Member",
        team_name="Manual New Team"
    )

    player = database.get_player_by_name(
        "Manual Moved Player"
    )

    new_team_member = database.get_player_by_name(
        "Manual New Team Member"
    )

    assert player is not None
    assert new_team_member is not None

    original_team_id = player[5]
    new_team_id = new_team_member[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Moved Player Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Moved Player Drop",
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

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=3,
        evidence_path="manual/moved-player.png",
        evidence_sha256="8" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["team_id"] == original_team_id

    database.change_player_team(
        player[0],
        new_team_id
    )

    moved_player = database.get_player_by_name(
        "Manual Moved Player"
    )

    assert moved_player is not None
    assert moved_player[5] == new_team_id

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert result["status"] == "ACCEPTED"

    # The player still exists, so personal credit is valid.
    assert result["player_id"] == player[0]
    assert result["player_deleted"] is False
    assert result["actual_contribution"] == 0.3
    assert result["normal_player_credit"] == 0.3

    # The evidence remains attached to the team the player was
    # on when the submission was made.
    assert result["team_id"] == original_team_id
    assert result["team_id"] != new_team_id

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                team_id,
                status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        evidence_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                player_id,
                team_id,
                partial_completion
            FROM partial_completions
            WHERE player_id = %s
              AND tile_id = %s
            ORDER BY team_id
            ''',
            (
                player[0],
                tile_id
            )
        )

        partial_rows = cursor.fetchall()

        cursor.execute(
            '''
            SELECT progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                original_team_id,
                condition_id
            )
        )

        original_team_progress = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                new_team_id,
                condition_id
            )
        )

        new_team_progress = cursor.fetchone()

    assert evidence_row == (
        original_team_id,
        "ACCEPTED"
    )

    assert len(partial_rows) == 1
    assert partial_rows[0][0] == player[0]
    assert partial_rows[0][1] == original_team_id
    assert float(partial_rows[0][2]) == 0.3

    assert original_team_progress == 3
    assert new_team_progress is None

    moved_player_after_review = database.get_player_by_name(
        "Manual Moved Player"
    )

    assert moved_player_after_review is not None
    assert moved_player_after_review[5] == new_team_id


def test_late_manual_evidence_keeps_original_team_after_player_moves():
    create_test_player(
        "Late Moved Player",
        team_name="Late Moved Original Team"
    )

    create_test_player(
        "Late Moved Finisher",
        team_name="Late Moved Original Team"
    )

    create_test_player(
        "Late Moved New Team Member",
        team_name="Late Moved New Team"
    )

    player = database.get_player_by_name(
        "Late Moved Player"
    )

    finisher = database.get_player_by_name(
        "Late Moved Finisher"
    )

    new_team_member = database.get_player_by_name(
        "Late Moved New Team Member"
    )

    assert player is not None
    assert finisher is not None
    assert new_team_member is not None

    original_team_id = player[5]
    new_team_id = new_team_member[5]

    assert finisher[5] == original_team_id
    assert new_team_id != original_team_id

    tile_id = database.add_tile_with_conditions(
        tile_name="Late Moved Player Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Late Moved Drop",
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

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/late-moved-test.png",
        evidence_sha256="3" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["team_id"] == original_team_id
    assert submission["banked_total_at_submission"] == 0.0

    # Another source completes the original team's tile while the
    # manual evidence is still waiting for review.
    with database.connect() as conn:
        cursor = conn.cursor()

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
                original_team_id,
                condition_id,
                10
            )
        )

        completion_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=original_team_id,
                tile_id=tile_id,
                finisher_player_id=finisher[0],
                return_details=True
            )
        )

        assert completion_result["completed"] is True

        conn.commit()

    # The credited player changes teams before staff reviews the
    # old submission.
    database.change_player_team(
        player[0],
        new_team_id
    )

    moved_player = database.get_player_by_name(
        "Late Moved Player"
    )

    assert moved_player is not None
    assert moved_player[5] == new_team_id

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff",
        award_lost_mvp=True
    )

    assert result["status"] == "ACCEPTED"
    assert result["late_review"] is True
    assert result["player_deleted"] is False

    # The submission remains attached to the team the player was
    # representing when they submitted it.
    assert result["team_id"] == original_team_id
    assert result["team_id"] != new_team_id

    assert result["potential_contribution"] == 0.4
    assert result["actual_contribution"] == 0.0
    assert result["lost_mvp_contribution"] == 0.4

    assert result["award_lost_mvp_requested"] is True
    assert result["late_review_contribution"] == 0.4
    assert result["late_review_points"] == 1.6

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                team_id,
                contribution,
                points_awarded,
                credit_type
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        credit_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT
                team_id,
                player_points
            FROM players
            WHERE player_id = %s
            ''',
            (player[0],)
        )

        player_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (original_team_id,)
        )

        original_team_points = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (new_team_id,)
        )

        new_team_points = float(
            cursor.fetchone()[0]
        )

    assert credit_row is not None

    # Personal credit follows the player, but its audit attribution
    # remains against the original team.
    assert credit_row[0] == original_team_id
    assert float(credit_row[1]) == 0.4
    assert float(credit_row[2]) == 1.6
    assert credit_row[3] == "LATE_REVIEW"

    # The player is still a member of their new team and receives
    # the personal MVP globally.
    assert player_row[0] == new_team_id
    assert float(player_row[1]) == 1.6

    # The completed tile belongs only to the original team.
    assert original_team_points == 4.0
    assert new_team_points == 0.0


def test_manual_evidence_can_complete_tile_after_player_deleted():
    create_test_player(
        "Manual Deleted Player",
        team_name="Manual Deleted Player Team"
    )

    player = database.get_player_by_name(
        "Manual Deleted Player"
    )

    assert player is not None

    player_id = player[0]
    team_id = player[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Deleted Player Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Deleted Player Drop",
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

        # The original team has already completed 60% of the
        # route. The submitted evidence will provide the final
        # 40%, even though its credited player is later deleted.
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
                6
            )
        )

        conn.commit()

    submission = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/deleted-player.png",
        evidence_sha256="7" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["player_id"] == player_id
    assert submission["team_id"] == team_id

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            DELETE FROM players
            WHERE player_id = %s
            ''',
            (player_id,)
        )

        conn.commit()

    # The live player identity is gone, but the evidence keeps
    # its frozen name/team attribution for review and audit.
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                credited_player_name,
                team_id,
                status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        evidence_after_delete = cursor.fetchone()

    assert evidence_after_delete == (
        None,
        "Manual Deleted Player",
        team_id,
        "PENDING"
    )

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff"
    )

    assert result["status"] == "ACCEPTED"

    assert result["player_id"] is None
    assert result["credited_player_name"] == "Manual Deleted Player"
    assert result["player_deleted"] is True

    assert result["team_id"] == team_id
    assert result["tile_id"] == tile_id

    assert result["raw_progress"] == 10
    assert result["route_progress"] == 1.0
    assert result["route_progress_delta"] == 0.4

    # The evidence still contributes to the team's board state,
    # but the deleted player receives no personal credit.
    assert result["actual_contribution"] == 0.4
    assert result["completion_remainder"] == 0.0
    assert result["normal_player_credit"] == 0.0

    assert result["potential_contribution"] == 0.4
    assert result["lost_mvp_contribution"] == 0.0

    # 40% is banked as uncredited evidence contribution before
    # the completion helper fills the remaining 60% as further
    # uncredited team contribution.
    assert result["banked_total"] == 0.4

    assert result["ready"] is True
    assert result["completed"] is True

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution,
                completed
            FROM manual_evidence_progress
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        progress_row = cursor.fetchone()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM player_tile_credits
            WHERE tile_id = %s
              AND team_id = %s
            ''',
            (
                tile_id,
                team_id
            )
        )

        personal_credit_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team_id,)
        )

        team_points = float(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        completed_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM partial_completions
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        partial_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT
                player_id,
                credited_player_name,
                team_id,
                status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        final_evidence = cursor.fetchone()

    assert float(progress_row[0]) == 0.4
    assert float(progress_row[1]) == 0.0
    assert float(progress_row[2]) == 0.0
    assert float(progress_row[3]) == 0.4
    assert float(progress_row[4]) == 0.0
    assert progress_row[5] is True

    assert personal_credit_count == 0

    assert team_points == 4.0
    assert completed_count == 1
    assert partial_count == 0

    assert final_evidence == (
        None,
        "Manual Deleted Player",
        team_id,
        "ACCEPTED"
    )


def test_deleted_player_cannot_receive_discretionary_late_review_mvp():
    create_test_player(
        "Deleted Late Evidence Player",
        team_name="Deleted Late Evidence Team"
    )

    create_test_player(
        "Deleted Late Evidence Finisher",
        team_name="Deleted Late Evidence Team"
    )

    player = database.get_player_by_name(
        "Deleted Late Evidence Player"
    )

    finisher = database.get_player_by_name(
        "Deleted Late Evidence Finisher"
    )

    assert player is not None
    assert finisher is not None
    assert player[5] == finisher[5]

    player_id = player[0]
    team_id = player[5]

    tile_id = database.add_tile_with_conditions(
        tile_name="Deleted Late Evidence Test Tile",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Deleted Late Drop",
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

    submission = database.add_manual_evidence(
        player_id=player_id,
        condition_id=condition_id,
        amount=4,
        evidence_path="manual/deleted-late-test.png",
        evidence_sha256="2" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    assert submission["player_id"] == player_id
    assert submission["team_id"] == team_id
    assert submission["banked_total_at_submission"] == 0.0

    # Another source completes the tile while this evidence is
    # still waiting for review.
    with database.connect() as conn:
        cursor = conn.cursor()

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
                10
            )
        )

        completion_result = (
            database._complete_tile_with_contributions(
                cursor=cursor,
                team_id=team_id,
                tile_id=tile_id,
                finisher_player_id=finisher[0],
                return_details=True
            )
        )

        assert completion_result["completed"] is True

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team_id,)
        )

        team_points_before_review = float(
            cursor.fetchone()[0]
        )

        conn.commit()

    # The credited player is deleted after submitting their
    # evidence but before staff reviews it.
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            DELETE FROM players
            WHERE player_id = %s
            ''',
            (player_id,)
        )

        conn.commit()

    result = database.accept_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=54321,
        reviewer_name="Reviewing Staff",
        award_lost_mvp=True
    )

    assert result["status"] == "ACCEPTED"
    assert result["late_review"] is True
    assert result["player_deleted"] is True
    assert result["player_id"] is None

    # The evidence remains historically attributable by its frozen
    # player name even though the live player row is gone.
    assert (
        result["credited_player_name"]
        == "Deleted Late Evidence Player"
    )

    # The evidence had 40% potential when submitted, but because
    # the tile completed before review it has no live contribution.
    assert result["potential_contribution"] == 0.4
    assert result["actual_contribution"] == 0.0
    assert result["lost_mvp_contribution"] == 0.4

    # Staff explicitly requested the discretionary award, but a
    # deleted player can never receive personal MVP credit.
    assert result["award_lost_mvp_requested"] is True
    assert result["late_review_contribution"] == 0.0
    assert result["late_review_points"] == 0.0

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                credited_player_name,
                team_id,
                status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        final_evidence = cursor.fetchone()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM player_tile_credits
            WHERE evidence_id = %s
              AND credit_type = 'LATE_REVIEW'
            ''',
            (submission["evidence_id"],)
        )

        late_credit_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            '''
            SELECT team_points
            FROM teams
            WHERE team_id = %s
            ''',
            (team_id,)
        )

        team_points_after_review = float(
            cursor.fetchone()[0]
        )

    assert final_evidence == (
        None,
        "Deleted Late Evidence Player",
        team_id,
        "ACCEPTED"
    )

    assert late_credit_count == 0

    # The team keeps the tile it already completed, but reviewing
    # the deleted player's evidence cannot score it a second time.
    assert team_points_before_review == 4.0
    assert team_points_after_review == 4.0


def test_reject_pending_manual_evidence_records_decision():
    create_test_player(
        "Manual Reject Tester",
        team_name="Manual Reject Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Reject Test Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    player = database.get_player_by_name(
        "Manual Reject Tester"
    )

    assert player is not None

    condition_id = database.get_tile_conditions(
        tile_id
    )[0][0]

    submission = database.add_manual_evidence(
        player_id=player[0],
        condition_id=condition_id,
        amount=1,
        description="Manual rejection test.",
        evidence_path="manual/reject-test.png",
        evidence_sha256="b" * 64,
        submission_source="DISCORD",
        submitter_id=12345,
        submitter_name="Submitting Staff"
    )

    result = database.reject_pending_manual_evidence(
        evidence_id=submission["evidence_id"],
        review_source="DISCORD",
        reviewer_id=67890,
        reviewer_name="Reviewing Staff",
        reason="Evidence does not clearly show completion."
    )

    assert result["status"] == "REJECTED"

    decision = database.get_staff_review_decision(
        "MANUAL_EVIDENCE",
        submission["evidence_id"]
    )

    assert decision is not None
    assert decision[3] == "REJECT"
    assert decision[4] == "DISCORD"
    assert decision[5] == 67890
    assert decision[6] == "Reviewing Staff"
    assert (
        decision[7]
        == "Evidence does not clearly show completion."
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (submission["evidence_id"],)
        )

        assert cursor.fetchone()[0] == "REJECTED"

        cursor.execute(
            '''
            SELECT progress
            FROM tile_condition_progress
            WHERE team_id = %s
              AND condition_id = %s
            ''',
            (
                player[5],
                condition_id
            )
        )

        assert cursor.fetchone() is None

def test_manual_evidence_refuses_killcount_and_experience():
    create_test_player(
        "Manual Automation Tester",
        team_name="Manual Automation Team"
    )

    player = database.get_player_by_name(
        "Manual Automation Tester"
    )

    assert player is not None

    for condition_type, trigger in (
        ("KILLCOUNT", "Vorkath"),
        ("EXPERIENCE", "attack")
    ):
        tile_id = database.add_tile_with_conditions(
            tile_name=(
                f"Manual Evidence {condition_type} Test"
            ),
            tile_points=1,
            tile_rules="",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": condition_type,
                    "condition_trigger": trigger,
                    "target": 1
                }
            ]
        )

        condition_id = database.get_tile_conditions(
            tile_id
        )[0][0]

        with pytest.raises(
            ValueError,
            match=(
                "Manual evidence cannot be submitted for "
                "KILLCOUNT or EXPERIENCE conditions."
            )
        ):
            database.add_manual_evidence(
                player_id=player[0],
                condition_id=condition_id,
                amount=1,
                evidence_path="manual/invalid.png",
                evidence_sha256="c" * 64,
                submission_source="DISCORD",
                submitter_id=12345,
                submitter_name="Test Staff"
            )


def test_manual_evidence_submission_options_hide_automation_only_conditions():
    create_test_player(
        "Manual Options Tester",
        team_name="Manual Options Team"
    )

    player = database.get_player_by_name(
        "Manual Options Tester"
    )

    assert player is not None

    tile_id = database.add_tile_with_conditions(
        tile_name="Manual Evidence Options Type Test",
        tile_points=3,
        tile_rules="Test rules",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Manual Options Drop",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "PET",
                "condition_trigger": "Manual Options Pet",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "METRIC",
                "condition_trigger": "manual_options_metric",
                "target": 5
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "Manual Options Task",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "KILLCOUNT",
                "condition_trigger": "Vorkath",
                "target": 10
            },
            {
                "completion_path": 1,
                "condition_type": "EXPERIENCE",
                "condition_trigger": "attack",
                "target": 1000
            }
        ]
    )

    result = database.get_manual_evidence_submission_options(
        player[0]
    )

    assert result["player_id"] == player[0]
    assert result["player_name"] == "Manual Options Tester"
    assert result["team_id"] == player[5]

    tile_options = {
        tile["tile_id"]: tile
        for tile in result["tiles"]
    }

    assert tile_id in tile_options

    tile_option = tile_options[tile_id]

    assert tile_option["tile_name"] == (
        "Manual Evidence Options Type Test"
    )
    assert tile_option["tile_points"] == 3.0
    assert tile_option["tile_rules"] == "Test rules"

    condition_types = {
        condition["condition_type"]
        for condition in tile_option["conditions"]
    }

    assert condition_types == {
        "DROP",
        "PET",
        "METRIC",
        "MANUAL"
    }

    condition_triggers = {
        condition["condition_trigger"]
        for condition in tile_option["conditions"]
    }

    assert "Manual Options Drop" in condition_triggers
    assert "Manual Options Pet" in condition_triggers
    assert "manual_options_metric" in condition_triggers
    assert "Manual Options Task" in condition_triggers

    assert "Vorkath" not in condition_triggers
    assert "attack" not in condition_triggers

def test_manual_evidence_submission_options_hide_completed_tiles_and_all_parts():
    create_test_player(
        "Manual Completed Options Tester",
        team_name="Manual Completed Options Team"
    )

    player = database.get_player_by_name(
        "Manual Completed Options Tester"
    )

    assert player is not None

    team_id = player[5]

    all_tile_id = database.add_tile_with_conditions(
        tile_name="Manual Options ALL Test",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Completed ALL Part",
                "target": 2
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Incomplete ALL Part",
                "target": 3
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL"
            }
        ]
    )

    all_conditions = database.get_tile_conditions(
        all_tile_id
    )

    completed_all_condition_id = next(
        condition[0]
        for condition in all_conditions
        if condition[4] == "Completed ALL Part"
    )

    database.add_tile_condition_progress(
        team_id=team_id,
        condition_id=completed_all_condition_id,
        amount=2
    )

    completed_tile_id = database.add_tile_with_conditions(
        tile_name="Manual Options Completed Tile",
        tile_points=5,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "Completed Tile Task",
                "target": 1
            }
        ]
    )

    database.add_completed_tile(
        completed_tile_id,
        team_id
    )

    result = database.get_manual_evidence_submission_options(
        player[0]
    )

    tile_options = {
        tile["tile_id"]: tile
        for tile in result["tiles"]
    }

    assert all_tile_id in tile_options
    assert completed_tile_id not in tile_options

    all_triggers = {
        condition["condition_trigger"]
        for condition
        in tile_options[all_tile_id]["conditions"]
    }

    assert all_triggers == {
        "Incomplete ALL Part"
    }


def test_manual_evidence_submission_options_handle_unique_and_repeatable_n_of():
    create_test_player(
        "Manual N Of Options Tester",
        team_name="Manual N Of Options Team"
    )

    player = database.get_player_by_name(
        "Manual N Of Options Tester"
    )

    assert player is not None

    team_id = player[5]

    unique_tile_id = database.add_tile_with_conditions(
        tile_name="Manual Options Unique N Of Test",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Used Unique Part",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Unused Unique Part",
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

    unique_conditions = database.get_tile_conditions(
        unique_tile_id
    )

    used_unique_condition_id = next(
        condition[0]
        for condition in unique_conditions
        if condition[4] == "Used Unique Part"
    )

    database.add_tile_condition_progress(
        team_id=team_id,
        condition_id=used_unique_condition_id,
        amount=1
    )

    repeatable_tile_id = database.add_tile_with_conditions(
        tile_name="Manual Options Repeatable N Of Test",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "Repeatable Part",
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 3,
                "require_unique": False
            }
        ]
    )

    repeatable_condition_id = database.get_tile_conditions(
        repeatable_tile_id
    )[0][0]

    database.add_tile_condition_progress(
        team_id=team_id,
        condition_id=repeatable_condition_id,
        amount=1
    )

    result = database.get_manual_evidence_submission_options(
        player[0]
    )

    tile_options = {
        tile["tile_id"]: tile
        for tile in result["tiles"]
    }

    assert unique_tile_id in tile_options
    assert repeatable_tile_id in tile_options

    unique_triggers = {
        condition["condition_trigger"]
        for condition
        in tile_options[unique_tile_id]["conditions"]
    }

    assert unique_triggers == {
        "Unused Unique Part"
    }

    repeatable_triggers = {
        condition["condition_trigger"]
        for condition
        in tile_options[repeatable_tile_id]["conditions"]
    }

    assert repeatable_triggers == {
        "Repeatable Part"
    }


def test_manual_evidence_submission_options_hide_completed_sum_and_n_of_routes():
    create_test_player(
        "Manual Completed Route Options Tester",
        team_name="Manual Completed Route Options Team"
    )

    player = database.get_player_by_name(
        "Manual Completed Route Options Tester"
    )

    assert player is not None

    team_id = player[5]

    sum_tile_id = database.add_tile_with_conditions(
        tile_name="Manual Options Completed SUM Test",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "SUM Part One",
                "target": 10
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "SUM Part Two",
                "target": 10
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "SUM",
                "route_target": 3
            }
        ]
    )

    sum_conditions = database.get_tile_conditions(
        sum_tile_id
    )

    database.add_tile_condition_progress(
        team_id=team_id,
        condition_id=sum_conditions[0][0],
        amount=2
    )

    database.add_tile_condition_progress(
        team_id=team_id,
        condition_id=sum_conditions[1][0],
        amount=1
    )

    n_of_tile_id = database.add_tile_with_conditions(
        tile_name="Manual Options Completed N Of Test",
        tile_points=4,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "N Of Part One",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "N Of Part Two",
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 1,
                "require_unique": True
            }
        ]
    )

    n_of_condition_id = database.get_tile_conditions(
        n_of_tile_id
    )[0][0]

    database.add_tile_condition_progress(
        team_id=team_id,
        condition_id=n_of_condition_id,
        amount=1
    )

    result = database.get_manual_evidence_submission_options(
        player[0]
    )

    tile_ids = {
        tile["tile_id"]
        for tile in result["tiles"]
    }

    assert sum_tile_id not in tile_ids
    assert n_of_tile_id not in tile_ids
