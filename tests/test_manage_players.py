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
def manage_players_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Manage Players tests must only run against "
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


def create_admin_user():
    database.add_user(
        "Manage Players Admin",
        "test-password"
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET account_role = 'ADMIN'
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            ''',
            ("Manage Players Admin",)
        )


def login_admin(client):
    create_admin_user()

    response = client.post(
        "/login",
        data={
            "username": "Manage Players Admin",
            "password": "test-password"
        }
    )

    assert response.status_code == 302


def create_player(
    player_name,
    team_id,
    *,
    mvp_points=0,
    tile_contributions=0
):
    database.add_player(
        player_name,
        0,
        0,
        tile_contributions,
        team_id,
        0
    )

    player = database.get_player_by_name(player_name)

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE players
            SET player_points = %s
            WHERE player_id = %s
            ''',
            (
                mvp_points,
                player[0]
            )
        )

    return database.get_player_by_name(player_name)


def test_manage_players_roster_orders_teams_and_players():
    database.add_team(
        "Second Team",
        0,
        ""
    )
    database.add_team(
        "First Team",
        0,
        ""
    )
    database.add_team(
        "Empty Team",
        0,
        ""
    )

    second_team = database.get_team_by_name("Second Team")
    first_team = database.get_team_by_name("First Team")

    create_player(
        "Zulu",
        second_team[3]
    )
    create_player(
        "alpha",
        second_team[3]
    )
    create_player(
        "Bravo",
        first_team[3]
    )

    roster = database.get_manage_players_roster()

    assert [
        team["team_name"]
        for team in roster
    ] == [
        "Second Team",
        "First Team",
        "Empty Team"
    ]

    assert [
        player["player_name"]
        for player in roster[0]["players"]
    ] == [
        "alpha",
        "Zulu"
    ]

    assert roster[2]["players"] == []


def test_manage_players_page_renders_new_roster_fields(client):
    database.add_team(
        "Roster Team",
        0,
        ""
    )

    team = database.get_team_by_name("Roster Team")

    create_player(
        "Roster Player",
        team[3],
        mvp_points=4,
        tile_contributions=2.35
    )

    login_admin(client)

    response = client.get(
        "/player/players"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Manage Players" in page
    assert "Teams" in page
    assert "Players" in page
    assert "Roster Team" in page
    assert "Roster Player" in page
    assert "MVP Points" in page
    assert "Tile Contributions" in page
    assert "Linked Discord" in page
    assert "2.35" in page
    assert "Not linked" in page

    assert "Player ID" not in page
    assert "Deaths" not in page
    assert "GP Gained" not in page
    assert "Pet Count" not in page
    assert "New Player" not in page
    assert ">Edit<" not in page
    assert ">Delete<" not in page


def test_manage_players_page_shows_discord_identity(client):
    database.add_team(
        "Discord Team",
        0,
        ""
    )

    team = database.get_team_by_name("Discord Team")

    player = create_player(
        "Discord Player",
        team[3]
    )

    database.link_player_to_discord(
        player[0],
        123456789012345678,
        "Clan Nickname",
        "discord.username"
    )

    login_admin(client)

    response = client.get(
        "/player/players"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Clan Nickname" in page
    assert "(@discord.username)" in page
    assert "123456789012345678" not in page


def test_manage_players_page_handles_legacy_discord_link(client):
    database.add_team(
        "Legacy Team",
        0,
        ""
    )

    team = database.get_team_by_name("Legacy Team")

    player = create_player(
        "Legacy Player",
        team[3]
    )

    database.link_player_to_discord(
        player[0],
        987654321012345678
    )

    login_admin(client)

    response = client.get(
        "/player/players"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Linked — name not yet available" in page
    assert "987654321012345678" not in page


def test_manage_players_page_shows_empty_team(client):
    database.add_team(
        "No Players Team",
        0,
        ""
    )

    login_admin(client)

    response = client.get(
        "/player/players"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "No Players Team" in page
    assert "No players assigned" in page


def test_manage_players_page_requires_login(client):
    response = client.get(
        "/player/players"
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]