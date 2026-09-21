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
            RETURNING user_id
            ''',
            (
                email,
                account_role,
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
