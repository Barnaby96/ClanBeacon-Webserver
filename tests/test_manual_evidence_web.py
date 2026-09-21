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
from utils import completion_notifications, database


@pytest.fixture(autouse=True)
def manual_evidence_web_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Manual evidence web tests must only run against "
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
    is_admin=False,
    account_role=None,
    player_id=None
):
    database.add_user(
        username,
        password
    )

    if account_role is None:
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
                account_role = %s,
                player_id = %s
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            RETURNING user_id
            ''',
            (
                email,
                account_role,
                player_id,
                username
            )
        )

        user_id = cursor.fetchone()[0]

    return user_id


def login_admin(client):
    create_test_user(
        "Manual Web Admin",
        "manual-web-admin@example.test",
        "test-password",
        is_admin=True
    )

    response = client.post(
        "/login",
        data={
            "username": "Manual Web Admin",
            "password": "test-password"
        }
    )

    assert response.status_code == 302


def test_admin_review_page_shows_pending_manual_evidence(
    client,
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_pending_dink_event_review_rows",
        lambda: []
    )

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: []
    )

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: [
            {
                "evidence_id": 701,
                "credited_player_name": "Discord Manual Tester",
                "team_name": "Manual Team",
                "tile_name": "Manual Tile",
                "condition_trigger": "Manual Drop",
                "condition_type": "DROP",
                "condition_target": 3,
                "condition_progress_at_submission": 1,
                "amount": 2,
                "description": "Discord manual notes",
                "evidence_path": "uploads/manual_evidence/test.png",
                "submission_source": "DISCORD",
                "submitter_name": "Discord Submitter",
                "evidence_author_name": "Discord Author",
                "evidence_codeword_at_submission": "Blackout Sky",
                "submitted_at": "2026-09-21 18:00:00",
                "discord_message_id": "123456789"
            },
            {
                "evidence_id": 702,
                "credited_player_name": "Web Manual Tester",
                "team_name": "Web Team",
                "tile_name": "Web Tile",
                "condition_trigger": "Web Pet",
                "condition_type": "PET",
                "condition_target": 1,
                "condition_progress_at_submission": 0,
                "amount": 1,
                "description": "Web manual notes",
                "evidence_path": None,
                "submission_source": "WEB",
                "submitter_name": "Web Submitter",
                "evidence_author_name": None,
                "evidence_codeword_at_submission": "Blackout Sky",
                "submitted_at": "2026-09-21 18:05:00",
                "discord_message_id": None
            }
        ]
    )

    login_admin(
        client
    )

    response = client.get(
        "/admin/dink_events"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "There are no automatic submissions waiting for review." in page
    assert "Pending Manual Evidence" in page
    assert "Discord Manual Tester" in page
    assert "Web Manual Tester" in page
    assert "Discord" in page
    assert "Web dashboard" in page
    assert "Blackout Sky" in page
    assert "accept_manual_evidence" in page
    assert "accept_manual_evidence_with_mvp" in page
    assert "reject_manual_evidence" in page


def test_admin_can_accept_pending_manual_evidence_from_web(
    client,
    monkeypatch
):
    accept_calls = []
    completion_calls = []

    def accept_pending_manual_evidence(**kwargs):
        accept_calls.append(
            kwargs
        )

        return {
            "status": "ACCEPTED",
            "newly_completed": True,
            "team_id": 10,
            "tile_id": 20
        }

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        accept_pending_manual_evidence
    )

    monkeypatch.setattr(
        completion_notifications,
        "notify_progress_completions",
        lambda completions: completion_calls.append(completions)
    )

    login_admin(
        client
    )

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "accept_manual_evidence",
            "evidence_id": "701"
        }
    )

    assert response.status_code == 302
    assert len(accept_calls) == 1

    assert accept_calls[0]["evidence_id"] == 701
    assert accept_calls[0]["review_source"] == "WEB"
    assert accept_calls[0]["reviewer_name"] == "Manual Web Admin"
    assert accept_calls[0]["award_lost_mvp"] is False

    assert completion_calls == [
        [
            {
                "team_id": 10,
                "tile_id": 20,
                "completed": True
            }
        ]
    ]


def test_admin_can_accept_pending_manual_evidence_with_mvp_from_web(
    client,
    monkeypatch
):
    accept_calls = []

    def accept_pending_manual_evidence(**kwargs):
        accept_calls.append(
            kwargs
        )

        return {
            "status": "ACCEPTED",
            "newly_completed": False,
            "late_review_points": 1.5
        }

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        accept_pending_manual_evidence
    )

    monkeypatch.setattr(
        completion_notifications,
        "notify_progress_completions",
        lambda completions: pytest.fail(
            "No completion notification should be sent "
            "when the tile was not newly completed."
        )
    )

    login_admin(
        client
    )

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "accept_manual_evidence_with_mvp",
            "evidence_id": "701"
        }
    )

    assert response.status_code == 302
    assert len(accept_calls) == 1

    assert accept_calls[0]["evidence_id"] == 701
    assert accept_calls[0]["review_source"] == "WEB"
    assert accept_calls[0]["reviewer_name"] == "Manual Web Admin"
    assert accept_calls[0]["award_lost_mvp"] is True


def test_admin_can_reject_pending_manual_evidence_from_web(
    client,
    monkeypatch
):
    reject_calls = []

    def reject_pending_manual_evidence(**kwargs):
        reject_calls.append(
            kwargs
        )

        return {
            "status": "REJECTED"
        }

    monkeypatch.setattr(
        database,
        "reject_pending_manual_evidence",
        reject_pending_manual_evidence
    )

    login_admin(
        client
    )

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "reject_manual_evidence",
            "evidence_id": "701",
            "reason_code": "INSUFFICIENT_EVIDENCE",
            "reason": "Screenshot does not show enough detail."
        }
    )

    assert response.status_code == 302
    assert len(reject_calls) == 1

    assert reject_calls[0]["evidence_id"] == 701
    assert reject_calls[0]["review_source"] == "WEB"
    assert reject_calls[0]["reviewer_name"] == "Manual Web Admin"
    assert reject_calls[0]["reason_code"] == "INSUFFICIENT_EVIDENCE"
    assert (
        reject_calls[0]["reason"]
        == "Screenshot does not show enough detail."
    )

def create_manual_submission_scenario(prefix):
    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO teams (
                team_name,
                team_points,
                team_webhook
            )
            VALUES (%s, 0, NULL)
            RETURNING team_id
            ''',
            (
                f"{prefix} Team",
            )
        )
        team_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            INSERT INTO players (
                player_name,
                deaths,
                gp_gained,
                tiles_completed,
                team_id,
                pet_count
            )
            VALUES (%s, 0, 0, 0, %s, 0)
            RETURNING player_id
            ''',
            (
                f"{prefix} Player",
                team_id
            )
        )
        player_id = cursor.fetchone()[0]

        conn.commit()

    database.add_tile_with_conditions(
        tile_name=f"{prefix} Manual Tile",
        tile_points=5,
        tile_rules="Upload proof for this manual tile.",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": f"{prefix} Task",
                "target": 1
            }
        ]
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                t.tile_id,
                c.condition_id
            FROM tiles t
            JOIN tile_conditions c
              ON c.tile_id = t.tile_id
            WHERE t.tile_name = %s
            ''',
            (
                f"{prefix} Manual Tile",
            )
        )

        tile_id, condition_id = cursor.fetchone()

    return {
        "team_id": team_id,
        "player_id": player_id,
        "tile_id": tile_id,
        "condition_id": condition_id,
        "player_name": f"{prefix} Player",
        "tile_name": f"{prefix} Manual Tile",
        "trigger": f"{prefix} Task"
    }


def login_dashboard_user(client, username, password):
    response = client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert response.status_code == 302


def test_linked_player_can_view_submit_evidence_page(
    client
):
    scenario = create_manual_submission_scenario(
        "Submit Own"
    )

    create_test_user(
        "Submit Own User",
        "submit-own@example.test",
        "test-password",
        player_id=scenario["player_id"]
    )

    login_dashboard_user(
        client,
        "Submit Own User",
        "test-password"
    )

    response = client.get(
        "/user/evidence/submit"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Submit Evidence" in page
    assert "Credited player:" in page
    assert scenario["player_name"] in page
    assert scenario["tile_name"] in page
    assert scenario["trigger"] in page
    assert "Player to credit:" not in page


def test_linked_player_can_submit_web_manual_evidence(
    client
):
    import io

    scenario = create_manual_submission_scenario(
        "Submit Web"
    )

    create_test_user(
        "Submit Web User",
        "submit-web@example.test",
        "test-password",
        player_id=scenario["player_id"]
    )

    login_dashboard_user(
        client,
        "Submit Web User",
        "test-password"
    )

    response = client.post(
        "/user/evidence/submit",
        data={
            "condition_id": str(scenario["condition_id"]),
            "amount": "1",
            "description": "Dashboard evidence upload",
            "evidence_file": (
                io.BytesIO(
                    b"web evidence"
                ),
                "evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 302
    assert (
        response.headers["Location"]
        .endswith(
            "/user/evidence/submit?player_id="
            f"{scenario['player_id']}"
        )
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                player_id,
                team_id,
                tile_id,
                condition_id,
                amount,
                status,
                submission_source,
                submitter_name,
                evidence_author_name,
                description
            FROM manual_evidence
            WHERE player_id = %s
            ''',
            (
                scenario["player_id"],
            )
        )

        evidence = cursor.fetchone()

    assert evidence is not None
    assert evidence[0] == scenario["player_id"]
    assert evidence[1] == scenario["team_id"]
    assert evidence[2] == scenario["tile_id"]
    assert evidence[3] == scenario["condition_id"]
    assert evidence[4] == 1
    assert evidence[5] == "PENDING"
    assert evidence[6] == "WEB"
    assert evidence[7] == "Submit Web User"
    assert evidence[8] == "Submit Web User"
    assert evidence[9] == "Dashboard evidence upload"


@pytest.mark.parametrize(
    "account_role",
    [
        "ADMIN",
        "ORGANISER"
    ]
)
def test_staff_can_submit_web_manual_evidence_for_any_player(
    client,
    account_role
):
    import io

    first_scenario = create_manual_submission_scenario(
        f"{account_role} Own"
    )
    second_scenario = create_manual_submission_scenario(
        f"{account_role} Other"
    )

    create_test_user(
        f"{account_role} Submitter",
        f"{account_role.lower()}-submitter@example.test",
        "test-password",
        account_role=account_role,
        player_id=first_scenario["player_id"]
    )

    login_dashboard_user(
        client,
        f"{account_role} Submitter",
        "test-password"
    )

    response = client.get(
        "/user/evidence/submit",
        query_string={
            "player_id": second_scenario["player_id"]
        }
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Player to credit:" in page
    assert second_scenario["player_name"] in page
    assert second_scenario["tile_name"] in page

    response = client.post(
        "/user/evidence/submit",
        data={
            "player_id": str(second_scenario["player_id"]),
            "condition_id": str(second_scenario["condition_id"]),
            "amount": "1",
            "description": "Staff submitted evidence",
            "evidence_file": (
                io.BytesIO(
                    b"staff evidence"
                ),
                "staff-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 302

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                player_id,
                submission_source,
                submitter_name,
                evidence_author_name,
                description
            FROM manual_evidence
            WHERE player_id = %s
            ''',
            (
                second_scenario["player_id"],
            )
        )

        evidence = cursor.fetchone()

    assert evidence is not None
    assert evidence[0] == second_scenario["player_id"]
    assert evidence[1] == "WEB"
    assert evidence[2] == f"{account_role} Submitter"
    assert evidence[3] == f"{account_role} Submitter"
    assert evidence[4] == "Staff submitted evidence"
