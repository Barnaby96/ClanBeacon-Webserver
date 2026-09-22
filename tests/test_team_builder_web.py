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
from utils import database, wom


@pytest.fixture(autouse=True)
def team_builder_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Team builder web tests must only run against "
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
            SET
                email = %s,
                account_role = %s
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            ''',
            (
                f"{username.casefold().replace(' ', '-')}@example.test",
                account_role,
                username
            )
        )


def login_admin(client):
    create_test_user(
        "Team Builder Admin",
        "test-password",
        account_role="ADMIN"
    )

    response = client.post(
        "/login",
        data={
            "username": "Team Builder Admin",
            "password": "test-password"
        }
    )

    assert response.status_code == 302


def make_group_payload():
    return {
        "id": 25798,
        "name": "Indoor Sky Test Group",
        "memberships": [
            {
                "player": {
                    "id": 1,
                    "username": "alpha",
                    "displayName": "Alpha"
                }
            },
            {
                "player": {
                    "id": 2,
                    "username": "bravo",
                    "displayName": "Bravo"
                }
            },
            {
                "player": {
                    "id": 3,
                    "username": "charlie",
                    "displayName": "Charlie"
                }
            },
            {
                "player": {
                    "id": 4,
                    "username": "delta",
                    "displayName": "Delta"
                }
            }
        ]
    }


def make_player_payload(
    name,
    total_level,
    combat_level,
    combat_skill_level
):
    skills = {
        "overall": {
            "level": total_level
        }
    }

    for skill_name in (
        "attack",
        "strength",
        "defence",
        "ranged",
        "prayer",
        "magic",
        "slayer"
    ):
        skills[skill_name] = {
            "level": combat_skill_level
        }

    return {
        "id": hash(name),
        "displayName": name,
        "combatLevel": combat_level,
        "latestSnapshot": {
            "data": {
                "skills": skills
            }
        }
    }


def test_team_builder_loads_wom_group_members(
    client,
    monkeypatch
):
    login_admin(
        client
    )

    monkeypatch.setattr(
        wom,
        "get_group",
        lambda group_id: make_group_payload()
    )

    response = client.get(
        "/player/players/balance?group_id=25798&team_count=2"
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "Team Builder" in html
    assert "Indoor Sky Test Group" in html
    assert "Alpha" in html
    assert "Bravo" in html
    assert "Charlie" in html
    assert "Delta" in html
    assert "Build Team Preview" in html
    assert 'name="player_names"' in html
    assert "checked" not in html


def test_team_builder_posts_selected_players_and_shows_preview(
    client,
    monkeypatch
):
    login_admin(
        client
    )

    monkeypatch.setattr(
        wom,
        "get_group",
        lambda group_id: make_group_payload()
    )

    player_payloads = {
        "Alpha": make_player_payload(
            "Alpha",
            total_level=2200,
            combat_level=126,
            combat_skill_level=99
        ),
        "Bravo": make_player_payload(
            "Bravo",
            total_level=2000,
            combat_level=110,
            combat_skill_level=90
        ),
        "Charlie": make_player_payload(
            "Charlie",
            total_level=1800,
            combat_level=95,
            combat_skill_level=75
        ),
        "Delta": make_player_payload(
            "Delta",
            total_level=1600,
            combat_level=80,
            combat_skill_level=60
        )
    }

    monkeypatch.setattr(
        wom,
        "get_player",
        lambda player_name: player_payloads[player_name]
    )

    response = client.post(
        "/player/players/balance",
        data={
            "group_id": "25798",
            "team_count": "2",
            "player_names": [
                "Alpha",
                "Bravo",
                "Charlie",
                "Delta"
            ]
        }
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "Suggested Team 1" in html
    assert "Suggested Team 2" in html
    assert "Alpha" in html
    assert "Bravo" in html
    assert "Charlie" in html
    assert "Delta" in html
    assert "Total Level" in html
    assert "Combat Level" in html
    assert "Skilling Score" in html
    assert "Why this team?" in html
    assert "Balance Score" in html
    assert "Total penalty" in html
    assert "Gap penalty" in html
    assert "Coverage penalty" in html
    assert "Lower is better." in html
    assert "Team 1 coverage" in html
    assert "Team 2 coverage" in html
    assert "Solo Boss Score" in html
    assert "Slayer Boss Score" in html
    assert "DT2 Boss Score" in html
    assert "End-game Boss Score" in html
    assert "Group Boss Score" in html
    assert "Raid Score" in html
    assert "Wilderness Boss Score" in html
    assert "Midgame Boss Score" in html
    assert "Activity Score" in html
    assert "Clue Activity Score" in html


def test_team_builder_requires_selected_players(
    client,
    monkeypatch
):
    login_admin(
        client
    )

    monkeypatch.setattr(
        wom,
        "get_group",
        lambda group_id: make_group_payload()
    )

    response = client.post(
        "/player/players/balance",
        data={
            "group_id": "25798",
            "team_count": "2"
        }
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "Select at least one player before building teams." in html
    assert "Suggested Team 1" not in html


def test_team_builder_reports_wom_lookup_failures(
    client,
    monkeypatch
):
    login_admin(
        client
    )

    monkeypatch.setattr(
        wom,
        "get_group",
        lambda group_id: make_group_payload()
    )

    def fake_get_player(player_name):
        if player_name == "Bravo":
            raise wom.WiseOldManError(
                "Unable to retrieve Wise Old Man player 'Bravo'."
            )

        return make_player_payload(
            player_name,
            total_level=1800,
            combat_level=100,
            combat_skill_level=80
        )

    monkeypatch.setattr(
        wom,
        "get_player",
        fake_get_player
    )

    response = client.post(
        "/player/players/balance",
        data={
            "group_id": "25798",
            "team_count": "2",
            "player_names": [
                "Alpha",
                "Bravo",
                "Charlie"
            ]
        }
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "Could not fetch WOM stats for: Bravo." in html
    assert "WOM Lookup Warnings" in html
    assert "Unable to retrieve Wise Old Man player &#39;Bravo&#39;." in html
    assert "Suggested Team 1" in html


def test_team_builder_uses_keep_apart_text_in_preview(
    client,
    monkeypatch
):
    login_admin(
        client
    )

    monkeypatch.setattr(
        wom,
        "get_group",
        lambda group_id: make_group_payload()
    )

    player_payloads = {
        "Alpha": make_player_payload(
            "Alpha",
            total_level=2200,
            combat_level=126,
            combat_skill_level=99
        ),
        "Bravo": make_player_payload(
            "Bravo",
            total_level=2100,
            combat_level=120,
            combat_skill_level=95
        ),
        "Charlie": make_player_payload(
            "Charlie",
            total_level=1800,
            combat_level=95,
            combat_skill_level=75
        ),
        "Delta": make_player_payload(
            "Delta",
            total_level=1600,
            combat_level=80,
            combat_skill_level=60
        )
    }

    monkeypatch.setattr(
        wom,
        "get_player",
        lambda player_name: player_payloads[player_name]
    )

    response = client.post(
        "/player/players/balance",
        data={
            "group_id": "25798",
            "team_count": "2",
            "keep_apart_text": "Alpha, Bravo",
            "player_names": [
                "Alpha",
                "Bravo",
                "Charlie",
                "Delta"
            ]
        }
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "Alpha, Bravo" in html
    assert "No keep-apart conflicts in this suggested team." in html
    assert "Keep-apart conflict:" not in html
