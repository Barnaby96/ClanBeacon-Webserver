import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from flask import session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import create_app
from routes.admin import team_routes as team_routes_module
from utils import database


TEST_WEBHOOK_URL = (
    "https://discord.com/api/webhooks/"
    "123456789012345678/"
    "team-management-test-token"
)


@pytest.fixture(autouse=True)
def team_management_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Team Management tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


@pytest.fixture()
def app():
    app = create_app()
    app.config["TESTING"] = True

    return app


@pytest.fixture()
def client(app):
    with app.test_client() as test_client:
        yield test_client


def create_dashboard_user(
    username,
    password,
    *,
    account_role="ADMIN"
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
            SET account_role = %s
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            ''',
            (
                account_role,
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


def create_team(
    team_name,
    webhook=None
):
    database.add_team(
        team_name,
        0,
        webhook
    )

    team = database.get_team_by_name(
        team_name
    )

    return team[3]


def test_tested_webhook_session_does_not_store_url(app):
    with app.test_request_context("/"):
        team_routes_module._remember_tested_webhook(
            12,
            TEST_WEBHOOK_URL
        )

        stored = session[
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
        ]

        assert stored["team_id"] == 12
        assert stored["fingerprint"] == (
            team_routes_module._webhook_fingerprint(
                TEST_WEBHOOK_URL
            )
        )
        assert TEST_WEBHOOK_URL not in str(stored)


def test_exact_tested_webhook_is_valid(app):
    with app.test_request_context("/"):
        team_routes_module._remember_tested_webhook(
            12,
            TEST_WEBHOOK_URL
        )

        assert (
            team_routes_module._is_tested_webhook_valid(
                12,
                TEST_WEBHOOK_URL
            )
            is True
        )


def test_changed_webhook_is_not_valid(app):
    with app.test_request_context("/"):
        team_routes_module._remember_tested_webhook(
            12,
            TEST_WEBHOOK_URL
        )

        changed_url = (
            TEST_WEBHOOK_URL
            + "changed"
        )

        assert (
            team_routes_module._is_tested_webhook_valid(
                12,
                changed_url
            )
            is False
        )


def test_tested_webhook_cannot_be_used_for_another_team(app):
    with app.test_request_context("/"):
        team_routes_module._remember_tested_webhook(
            12,
            TEST_WEBHOOK_URL
        )

        assert (
            team_routes_module._is_tested_webhook_valid(
                13,
                TEST_WEBHOOK_URL
            )
            is False
        )


def test_expired_webhook_test_is_rejected(
    app,
    monkeypatch
):
    monkeypatch.setattr(
        team_routes_module.time,
        "time",
        lambda: 1000
    )

    with app.test_request_context("/"):
        team_routes_module._remember_tested_webhook(
            12,
            TEST_WEBHOOK_URL
        )

        monkeypatch.setattr(
            team_routes_module.time,
            "time",
            lambda: (
                1000
                + team_routes_module.WEBHOOK_TEST_MAX_AGE_SECONDS
                + 1
            )
        )

        assert (
            team_routes_module._is_tested_webhook_valid(
                12,
                TEST_WEBHOOK_URL
            )
            is False
        )

        assert (
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
            not in session
        )


def test_test_team_webhook_sends_message_and_remembers_fingerprint(
    client,
    monkeypatch
):
    team_id = create_team(
        "Zamorak",
        webhook="https://discord.com/api/webhooks/999/old-token"
    )

    create_dashboard_user(
        "WebhookAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "WebhookAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    captured = {}

    def fake_send_test_webhook(
        webhook_url,
        message
    ):
        captured["webhook_url"] = webhook_url
        captured["message"] = message
        return True

    monkeypatch.setattr(
        team_routes_module,
        "send_test_webhook",
        fake_send_test_webhook
    )

    response = client.post(
        (
            f"/team/teams/edit/{team_id}"
            "/webhook/test"
        ),
        json={
            "webhook_url": TEST_WEBHOOK_URL
        }
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["success"] is True
    assert (
        "Test message sent successfully"
        in payload["message"]
    )

    assert captured == {
        "webhook_url": TEST_WEBHOOK_URL,
        "message": (
            f"{team_routes_module.BOT_NAME} Webhook Test\n"
            "This is a test message for team Zamorak."
        )
    }

    with client.session_transaction() as test_session:
        stored = test_session[
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
        ]

        assert stored["team_id"] == team_id

        assert stored["fingerprint"] == (
            team_routes_module._webhook_fingerprint(
                TEST_WEBHOOK_URL
            )
        )

        assert TEST_WEBHOOK_URL not in str(
            stored
        )

    team = database.get_team_by_id(
        team_id
    )

    assert team[2] == (
        "https://discord.com/api/webhooks/999/old-token"
    )


def test_failed_team_webhook_test_clears_previous_success(
    client,
    monkeypatch
):
    team_id = create_team(
        "Zamorak"
    )

    create_dashboard_user(
        "WebhookFailureAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "WebhookFailureAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    with client.session_transaction() as test_session:
        test_session[
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
        ] = {
            "team_id": team_id,
            "fingerprint": (
                team_routes_module._webhook_fingerprint(
                    TEST_WEBHOOK_URL
                )
            ),
            "tested_at": (
                team_routes_module.time.time()
            )
        }

    def failed_send_test_webhook(
        webhook_url,
        message
    ):
        raise RuntimeError(
            "Discord rejected the test webhook."
        )

    monkeypatch.setattr(
        team_routes_module,
        "send_test_webhook",
        failed_send_test_webhook
    )

    response = client.post(
        (
            f"/team/teams/edit/{team_id}"
            "/webhook/test"
        ),
        json={
            "webhook_url": TEST_WEBHOOK_URL
        }
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload == {
        "success": False,
        "message": "Discord rejected the test webhook."
    }

    with client.session_transaction() as test_session:
        assert (
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
            not in test_session
        )


def test_tested_team_webhook_can_be_saved(
    client
):
    old_webhook = (
        "https://discord.com/api/webhooks/"
        "999/old-token"
    )

    team_id = create_team(
        "Zamorak",
        webhook=old_webhook
    )

    create_dashboard_user(
        "WebhookSaveAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "WebhookSaveAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    with client.session_transaction() as test_session:
        test_session[
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
        ] = {
            "team_id": team_id,
            "fingerprint": (
                team_routes_module._webhook_fingerprint(
                    TEST_WEBHOOK_URL
                )
            ),
            "tested_at": (
                team_routes_module.time.time()
            )
        }

    response = client.post(
        (
            f"/team/teams/edit/{team_id}"
            "/webhook/save"
        ),
        json={
            "webhook_url": TEST_WEBHOOK_URL
        }
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload == {
        "success": True,
        "message": (
            "Team Discord webhook saved successfully."
        )
    }

    team = database.get_team_by_id(
        team_id
    )

    assert team[2] == TEST_WEBHOOK_URL

    with client.session_transaction() as test_session:
        assert (
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
            not in test_session
        )


def test_untested_team_webhook_cannot_be_saved(
    client
):
    old_webhook = (
        "https://discord.com/api/webhooks/"
        "999/old-token"
    )

    team_id = create_team(
        "Zamorak",
        webhook=old_webhook
    )

    create_dashboard_user(
        "WebhookUntestedAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "WebhookUntestedAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.post(
        (
            f"/team/teams/edit/{team_id}"
            "/webhook/save"
        ),
        json={
            "webhook_url": TEST_WEBHOOK_URL
        }
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload == {
        "success": False,
        "message": (
            "Test this exact webhook successfully "
            "before saving it."
        )
    }

    team = database.get_team_by_id(
        team_id
    )

    assert team[2] == old_webhook


def test_changed_team_webhook_cannot_be_saved_after_test(
    client
):
    old_webhook = (
        "https://discord.com/api/webhooks/"
        "999/old-token"
    )

    team_id = create_team(
        "Zamorak",
        webhook=old_webhook
    )

    create_dashboard_user(
        "WebhookChangedAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "WebhookChangedAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    with client.session_transaction() as test_session:
        test_session[
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
        ] = {
            "team_id": team_id,
            "fingerprint": (
                team_routes_module._webhook_fingerprint(
                    TEST_WEBHOOK_URL
                )
            ),
            "tested_at": (
                team_routes_module.time.time()
            )
        }

    changed_webhook_url = (
        TEST_WEBHOOK_URL
        + "changed"
    )

    response = client.post(
        (
            f"/team/teams/edit/{team_id}"
            "/webhook/save"
        ),
        json={
            "webhook_url": changed_webhook_url
        }
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload == {
        "success": False,
        "message": (
            "Test this exact webhook successfully "
            "before saving it."
        )
    }

    team = database.get_team_by_id(
        team_id
    )

    assert team[2] == old_webhook


def test_team_webhook_can_be_removed(
    client
):
    team_id = create_team(
        "Zamorak",
        webhook=TEST_WEBHOOK_URL
    )

    create_dashboard_user(
        "WebhookRemoveAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "WebhookRemoveAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    with client.session_transaction() as test_session:
        test_session[
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
        ] = {
            "team_id": team_id,
            "fingerprint": (
                team_routes_module._webhook_fingerprint(
                    TEST_WEBHOOK_URL
                )
            ),
            "tested_at": (
                team_routes_module.time.time()
            )
        }

    response = client.post(
        (
            f"/team/teams/edit/{team_id}"
            "/webhook/remove"
        )
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload == {
        "success": True,
        "message": (
            "Team Discord webhook removed successfully."
        )
    }

    team = database.get_team_by_id(
        team_id
    )

    assert team[2] is None

    with client.session_transaction() as test_session:
        assert (
            team_routes_module.WEBHOOK_TEST_SESSION_KEY
            not in test_session
        )


def test_team_webhook_remove_succeeds_when_already_unconfigured(
    client
):
    team_id = create_team(
        "Zamorak",
        webhook=None
    )

    create_dashboard_user(
        "WebhookRemoveEmptyAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "WebhookRemoveEmptyAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.post(
        (
            f"/team/teams/edit/{team_id}"
            "/webhook/remove"
        )
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload == {
        "success": True,
        "message": (
            "Team Discord webhook removed successfully."
        )
    }

    team = database.get_team_by_id(
        team_id
    )

    assert team[2] is None


def test_edit_team_only_updates_team_details(
    client
):
    old_webhook = (
        "https://discord.com/api/webhooks/"
        "999/original-token"
    )

    team_id = create_team(
        "Zamorak",
        webhook=old_webhook
    )

    database.add_team_points(
        team_id,
        42
    )

    database.set_team_discord_role_id(
        team_id,
        123456789012345678
    )

    create_dashboard_user(
        "TeamDetailsAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "TeamDetailsAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.post(
        f"/team/teams/edit/{team_id}",
        data={
            "team_name": "Saradomin",
            "team_points": "9999",
            "team_webhook": (
                "https://discord.com/api/webhooks/"
                "888/replacement-token"
            ),
            "discord_role_id": "987654321098765432"
        }
    )

    assert response.status_code == 302

    team = database.get_team_by_id(
        team_id
    )

    assert team[0] == "Saradomin"
    assert team[1] == 42
    assert team[2] == old_webhook
    assert team[4] == 123456789012345678


def test_edit_team_rejects_blank_team_name(
    client
):
    team_id = create_team(
        "Zamorak"
    )

    create_dashboard_user(
        "BlankTeamNameAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "BlankTeamNameAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.post(
        f"/team/teams/edit/{team_id}",
        data={
            "team_name": "   "
        }
    )

    assert response.status_code == 302

    team = database.get_team_by_id(
        team_id
    )

    assert team[0] == "Zamorak"


def test_edit_team_rejects_case_insensitive_duplicate_name(
    client
):
    existing_team_id = create_team(
        "Guthix"
    )

    team_id = create_team(
        "Zamorak"
    )

    create_dashboard_user(
        "DuplicateTeamNameAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "DuplicateTeamNameAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.post(
        f"/team/teams/edit/{team_id}",
        data={
            "team_name": "gUtHiX"
        }
    )

    assert response.status_code == 302

    existing_team = database.get_team_by_id(
        existing_team_id
    )

    renamed_team = database.get_team_by_id(
        team_id
    )

    assert existing_team[0] == "Guthix"
    assert renamed_team[0] == "Zamorak"


def test_edit_team_page_uses_redesigned_controls(
    client
):
    team_id = create_team(
        "Zamorak",
        webhook=TEST_WEBHOOK_URL
    )

    database.set_team_discord_role_id(
        team_id,
        123456789012345678
    )

    create_dashboard_user(
        "EditTeamPageAdmin",
        "test-password"
    )

    login_response = login_dashboard_user(
        client,
        "EditTeamPageAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        f"/team/teams/edit/{team_id}"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert "Team Details" in page_html
    assert "Discord Integration" in page_html
    assert "Save Team Details" in page_html
    assert "Manage Webhook" in page_html
    assert "Remove Photo" not in page_html

    assert 'name="team_name"' in page_html
    assert 'id="webhook-url"' in page_html
    assert 'id="test-webhook"' in page_html
    assert 'id="save-webhook"' in page_html
    assert 'id="remove-webhook"' in page_html

    assert 'name="team_points"' not in page_html
    assert 'name="team_webhook"' not in page_html
    assert 'name="discord_role_id"' not in page_html

    assert TEST_WEBHOOK_URL not in page_html