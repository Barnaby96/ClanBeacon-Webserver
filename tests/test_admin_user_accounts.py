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
def admin_user_accounts_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Admin user account tests must only run against "
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
    password,
    account_role="PLAYER"
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
                email = %s,
                account_role = %s,
                is_admin = %s
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            RETURNING user_id
            ''',
            (
                f"{username.casefold().replace(' ', '-')}@example.test",
                account_role,
                account_role in {
                    "ADMIN",
                    "ORGANISER"
                },
                username
            )
        )

        user_id = cursor.fetchone()[0]
        conn.commit()

    return user_id


def login_user(
    client,
    username,
    password
):
    response = client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert response.status_code == 302


def test_admin_home_links_to_user_accounts(
    client
):
    create_test_user(
        "Organiser User",
        "test-password",
        account_role="ORGANISER"
    )
    login_user(
        client,
        "Organiser User",
        "test-password"
    )

    response = client.get(
        "/admin/",
        follow_redirects=True
    )

    html = response.get_data(
        as_text=True
    )

    assert response.status_code == 200
    assert "Admin Dashboard" in html
    assert "User Accounts" in html
    assert "/admin/user_accounts" in html


def test_organiser_can_promote_player_to_admin(
    client
):
    create_test_user(
        "Organiser User",
        "test-password",
        account_role="ORGANISER"
    )
    player_user_id = create_test_user(
        "Player User",
        "test-password",
        account_role="PLAYER"
    )

    login_user(
        client,
        "Organiser User",
        "test-password"
    )

    response = client.post(
        "/admin/user_accounts",
        data={
            "user_id": str(player_user_id),
            "account_role": "ADMIN"
        },
        follow_redirects=True
    )

    html = response.get_data(
        as_text=True
    )
    updated_user = database.get_user_by_username(
        "Player User"
    )

    assert response.status_code == 200
    assert "Updated Player User to ADMIN." in html
    assert updated_user.account_role == "ADMIN"
    assert updated_user.is_admin


def test_admin_cannot_manage_user_accounts(
    client
):
    create_test_user(
        "Admin User",
        "test-password",
        account_role="ADMIN"
    )

    login_user(
        client,
        "Admin User",
        "test-password"
    )

    response = client.get(
        "/admin/user_accounts"
    )

    assert response.status_code == 403


def test_organiser_cannot_demote_self(
    client
):
    organiser_user_id = create_test_user(
        "Organiser User",
        "test-password",
        account_role="ORGANISER"
    )

    login_user(
        client,
        "Organiser User",
        "test-password"
    )

    response = client.post(
        "/admin/user_accounts",
        data={
            "user_id": str(organiser_user_id),
            "account_role": "PLAYER"
        },
        follow_redirects=True
    )

    html = response.get_data(
        as_text=True
    )
    organiser_user = database.get_user_by_username(
        "Organiser User"
    )

    assert response.status_code == 200
    assert "You cannot remove your own organiser access." in html
    assert organiser_user.account_role == "ORGANISER"
    assert organiser_user.is_organiser
