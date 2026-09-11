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
from utils import database


@pytest.fixture(autouse=True)
def dink_audit_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Dink audit tests must only run against "
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


def test_admin_can_view_dink_auth_audit(client):
    create_test_user(
        "Audit Admin",
        "audit-admin@example.test",
        "test-password",
        is_admin=True
    )

    database.record_dink_auth_failure(
        failure_reason="MISSING_SECRET",
        request_format="JSON",
        claimed_player_name="Audit Page Tester",
        claimed_dink_account_hash="audit-test-hash",
        claimed_event_type="LOOT",
        source_ip="127.0.0.1",
        user_agent="Bingo bot audit regression test"
    )

    login_response = login_test_user(
        client,
        "audit-admin@example.test",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/admin/dink_audit"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Blocked Connection Attempts" in page
    assert "Missing connection key" in page
    assert "Audit Page Tester" in page
    assert "audit-test-hash" in page
    assert "LOOT" in page
    assert "JSON" in page
    assert "127.0.0.1" in page
    assert "Bingo bot audit regression test" in page


def test_non_admin_cannot_view_dink_auth_audit(client):
    create_test_user(
        "Audit User",
        "audit-user@example.test",
        "test-password"
    )

    login_response = login_test_user(
        client,
        "audit-user@example.test",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/admin/dink_audit"
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_view_dink_auth_audit(
    client
):
    response = client.get(
        "/admin/dink_audit"
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]