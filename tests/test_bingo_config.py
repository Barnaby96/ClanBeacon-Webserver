import os
import sys
from datetime import timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import create_app
import routes.admin.admin_routes as admin_routes_module
from utils import database


@pytest.fixture(autouse=True)
def bingo_config_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Bingo config tests must only run against "
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
        "Bingo Setup Admin",
        "test-password"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            UPDATE users
            SET account_role = 'ORGANISER'
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            ''',
            ("Bingo Setup Admin",)
        )


def login_admin(client):
    response = client.post(
        "/login",
        data={
            "username": "Bingo Setup Admin",
            "password": "test-password"
        }
    )

    assert response.status_code == 302


def mock_wom_competition():
    return {
        "id": 123456,
        "title": "Test Bingo Competition",
        "type": "team",
        "startsAt": "2026-09-05T16:00:00.000Z",
        "endsAt": "2026-09-12T16:00:00.000Z",
        "participations": [
            {
                "teamName": "Test Team",
                "playerId": 987654,
                "player": {
                    "id": 987654,
                    "displayName": "Test Player"
                }
            }
        ]
    }


def test_evidence_codeword_can_be_saved_and_retrieved():
    assert database.get_evidence_codeword() is None

    database.set_evidence_codeword(
        "  Blackout Sky  "
    )

    assert database.get_evidence_codeword() == (
        "Blackout Sky"
    )


def test_evidence_codeword_refuses_blank_value():
    with pytest.raises(
        ValueError,
        match="Evidence codeword cannot be blank."
    ):
        database.set_evidence_codeword(
            "   "
        )


def test_bingo_config_fields_do_not_overwrite_each_other():
    database.set_evidence_codeword(
        "Blackout Sky"
    )

    database.set_wom_competition_id(
        123456
    )

    assert database.get_evidence_codeword() == (
        "Blackout Sky"
    )
    assert database.get_wom_competition_id() == 123456

    database.set_evidence_codeword(
        "New Bingo Code"
    )

    assert database.get_evidence_codeword() == (
        "New Bingo Code"
    )
    assert database.get_wom_competition_id() == 123456


def test_wom_import_saves_config_and_competition_timing():
    result = database.import_wom_competition(
        123456,
        {},
        "  Blackout Sky  ",
        competition_starts_at=(
            "2026-09-05T16:00:00.000Z"
        ),
        competition_ends_at=(
            "2026-09-12T16:00:00.000Z"
        )
    )

    assert result["imported"] is True
    assert database.get_wom_competition_id() == 123456
    assert database.get_evidence_codeword() == (
        "Blackout Sky"
    )

    timing = database.get_wom_competition_timing()

    assert timing["starts_at"].astimezone(
        timezone.utc
    ).isoformat() == (
        "2026-09-05T16:00:00+00:00"
    )
    assert timing["ends_at"].astimezone(
        timezone.utc
    ).isoformat() == (
        "2026-09-12T16:00:00+00:00"
    )


@pytest.mark.parametrize(
    "new_competition_id",
    [123456, 654321, None]
)
def test_setting_competition_id_handles_existing_timing(
    new_competition_id
):
    database.import_wom_competition(
        123456,
        {},
        "Timing Test",
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    original_timing = database.get_wom_competition_timing()
    assert original_timing is not None

    database.set_wom_competition_id(
        new_competition_id
    )

    assert database.get_wom_competition_id() == (
        new_competition_id
    )
    assert database.get_evidence_codeword() == "Timing Test"

    if new_competition_id == 123456:
        assert database.get_wom_competition_timing() == (
            original_timing
        )
    else:
        with database.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT wom_competition_starts_at,
                       wom_competition_ends_at
                FROM bingo_config
                WHERE config_id = 1
                """
            )
            assert cursor.fetchone() == (None, None)

        assert database.get_wom_competition_timing() is None


def test_wom_import_refuses_blank_evidence_codeword():
    with pytest.raises(
        ValueError,
        match="Evidence codeword cannot be blank."
    ):
        database.import_wom_competition(
            123456,
            {},
            "   "
        )

    assert database.get_wom_competition_id() is None
    assert database.get_evidence_codeword() is None


def test_wom_import_preview_shows_fresh_import_changes():
    plan = database.preview_wom_competition_import(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    assert plan["has_changes"] is True
    assert plan["has_conflicts"] is False
    assert plan["conflicts"] == []

    assert plan["teams_to_create"] == [
        {
            "team_name": "Test Team"
        }
    ]

    assert plan["players_to_create"] == [
        {
            "player_name": "Test Player",
            "team_name": "Test Team",
            "wom_player_id": 987654
        }
    ]

    assert plan["memberships_to_update"] == []
    assert plan["players_to_update"] == []

    changed_fields = {
        change["field"]
        for change in plan["config_changes"]
    }

    assert "wom_competition_id" in changed_fields
    assert "wom_competition_starts_at" in changed_fields
    assert "wom_competition_ends_at" in changed_fields
    assert "evidence_codeword" in changed_fields


def test_wom_import_preview_shows_no_changes_after_same_import():
    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    plan = database.preview_wom_competition_import(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    assert plan["has_changes"] is False
    assert plan["has_conflicts"] is False
    assert plan["conflicts"] == []
    assert plan["teams_to_create"] == []
    assert plan["players_to_create"] == []
    assert plan["players_to_update"] == []
    assert plan["memberships_to_update"] == []
    assert plan["config_changes"] == []


def test_wom_import_preview_shows_player_team_move_as_change():
    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    plan = database.preview_wom_competition_import(
        123456,
        {
            "Second Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    assert plan["has_changes"] is True
    assert plan["has_conflicts"] is False
    assert plan["conflicts"] == []

    assert plan["teams_to_create"] == [
        {
            "team_name": "Second Team"
        }
    ]

    assert plan["players_to_create"] == []
    assert plan["players_to_update"] == []

    assert plan["memberships_to_update"] == [
        {
            "player_name": "Test Player",
            "current_team_name": "Test Team",
            "new_team_name": "Second Team"
        }
    ]


def test_wom_import_updates_player_team_membership_from_wom():
    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    result = database.import_wom_competition(
        123456,
        {
            "Second Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    assert result["imported"] is True
    assert result["conflicts"] == []
    assert result["teams_created"] == 1
    assert result["players_created"] == 0
    assert result["players_reused"] == 1

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                teams.team_name,
                players.wom_player_id
            FROM players
            JOIN teams
              ON teams.team_id = players.team_id
            WHERE lower(players.player_name) = lower(%s)
            ''',
            ("Test Player",)
        )

        player_row = cursor.fetchone()

    assert player_row == (
        "Second Team",
        987654
    )


def test_bingo_setup_refuses_import_without_codeword(
    client,
    monkeypatch
):
    create_admin_user()
    login_admin(client)

    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_competition_details",
        lambda competition_id: mock_wom_competition()
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "competition_id": "123456",
            "action": "import",
            "evidence_codeword": ""
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        "Please enter an evidence codeword before "
        "confirming the import."
    ) in page

    assert database.get_wom_competition_id() is None
    assert database.get_evidence_codeword() is None

    assert database.get_team_by_name(
        "Test Team"
    ) is None

    assert database.get_player_by_name(
        "Test Player"
    ) is None


def test_bingo_setup_import_saves_codeword(
    client,
    monkeypatch
):
    create_admin_user()
    login_admin(client)

    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_competition_details",
        lambda competition_id: mock_wom_competition()
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "competition_id": "123456",
            "action": "import",
            "evidence_codeword": "  Blackout Sky  "
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Competition imported successfully." in page

    assert database.get_wom_competition_id() == 123456

    assert database.get_evidence_codeword() == (
        "Blackout Sky"
    )

    timing = database.get_wom_competition_timing()

    assert timing["starts_at"].astimezone(
        timezone.utc
    ).isoformat() == (
        "2026-09-05T16:00:00+00:00"
    )
    assert timing["ends_at"].astimezone(
        timezone.utc
    ).isoformat() == (
        "2026-09-12T16:00:00+00:00"
    )

    assert database.get_team_by_name(
        "Test Team"
    ) is not None

    assert database.get_player_by_name(
        "Test Player"
    ) is not None


def test_bingo_setup_preview_shows_no_changes_after_same_import(
    client,
    monkeypatch
):
    create_admin_user()
    login_admin(client)

    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_competition_details",
        lambda competition_id: mock_wom_competition()
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "competition_id": "123456"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "No import changes found." in page


def test_bingo_setup_preview_shows_codeword_field(
    client,
    monkeypatch
):
    create_admin_user()
    login_admin(client)

    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_competition_details",
        lambda competition_id: mock_wom_competition()
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "competition_id": "123456"
        }
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Test Bingo Competition" in page
    assert "Test Team" in page
    assert "Test Player" in page

    assert 'name="evidence_codeword"' in page
    assert "Evidence Codeword:" in page
    assert "Preview Changes" in page

    assert database.get_wom_competition_id() is None
    assert database.get_evidence_codeword() is None


def test_bingo_setup_preview_with_codeword_shows_import_plan(
    client,
    monkeypatch
):
    create_admin_user()
    login_admin(client)

    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_competition_details",
        lambda competition_id: mock_wom_competition()
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "competition_id": "123456",
            "action": "preview",
            "evidence_codeword": "Blackout Sky"
        }
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Planned Import Changes" in page
    assert "Teams to create" in page
    assert "Test Team" in page
    assert "Players to create" in page
    assert "Test Player" in page
    assert "Configuration changes" in page
    assert "Confirm Import" in page

    assert database.get_wom_competition_id() is None
    assert database.get_evidence_codeword() is None
    assert database.get_team_by_name(
        "Test Team"
    ) is None
    assert database.get_player_by_name(
        "Test Player"
    ) is None


def test_bingo_setup_preview_shows_wom_team_membership_move(
    client,
    monkeypatch
):
    create_admin_user()
    login_admin(client)

    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    moved_competition = mock_wom_competition()
    moved_competition["participations"][0]["teamName"] = "Second Team"

    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_competition_details",
        lambda competition_id: moved_competition
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "competition_id": "123456",
            "action": "preview",
            "evidence_codeword": "Blackout Sky"
        }
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Planned Import Changes" in page
    assert "Team memberships to update" in page
    assert "Test Player" in page
    assert "Test Team" in page
    assert "Second Team" in page
    assert "Confirm Import" in page

    assert database.get_team_by_name(
        "Second Team"
    ) is None

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT teams.team_name
            FROM players
            JOIN teams
              ON teams.team_id = players.team_id
            WHERE lower(players.player_name) = lower(%s)
            ''',
            ("Test Player",)
        )

        player_team = cursor.fetchone()

    assert player_team == (
        "Test Team",
    )


def test_bingo_setup_confirm_import_applies_wom_team_membership_move(
    client,
    monkeypatch
):
    create_admin_user()
    login_admin(client)

    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    moved_competition = mock_wom_competition()
    moved_competition["participations"][0]["teamName"] = "Second Team"

    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_competition_details",
        lambda competition_id: moved_competition
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "competition_id": "123456",
            "action": "import",
            "evidence_codeword": "Blackout Sky"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Competition imported successfully." in page
    assert database.get_team_by_name(
        "Second Team"
    ) is not None

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT teams.team_name
            FROM players
            JOIN teams
              ON teams.team_id = players.team_id
            WHERE lower(players.player_name) = lower(%s)
            ''',
            ("Test Player",)
        )

        player_team = cursor.fetchone()

    assert player_team == (
        "Second Team",
    )


def test_bingo_setup_shows_recent_wom_refresh_audit_rows(
    client
):
    database.record_wom_refresh_audit(
        requested_by_user_id=None,
        requested_by_username="Refresh Tester",
        result={
            "competition_id": 123456,
            "metrics_processed": 3,
            "players_processed": 12,
            "tiles_completed": [
                {
                    "tile_id": 1,
                    "team_id": 1,
                    "metric": "agility"
                },
                {
                    "tile_id": 2,
                    "team_id": 1,
                    "metric": "mining"
                }
            ],
            "errors": [
                {
                    "metric": "hunter",
                    "error": "Example warning"
                }
            ]
        }
    )

    create_admin_user()
    login_admin(client)

    response = client.get(
        "/admin/bingo_setup"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Recent WOM Refreshes" in page
    assert "Refresh Tester" in page
    assert "123456" in page
    compact_page = ''.join(
        page.split()
    )

    assert ">3<" in compact_page
    assert ">12<" in compact_page
    assert ">2<" in compact_page
    assert ">1<" in compact_page
    assert "hunter" in page
    assert "Example warning" in page

def test_bingo_setup_reset_refuses_wrong_password(
    client
):
    create_admin_user()
    login_admin(client)

    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    tile_id = database.add_tile(
        "Reset Safety Tile",
        "KILLCOUNT",
        "Vorkath",
        "1",
        "FALSE",
        1,
        1,
        5,
        "Test tile"
    )

    response = client.post(
        "/admin/bingo_setup",
        data={
            "action": "reset_bingo_data",
            "reset_password": "wrong-password",
            "reset_competition_id": "123456"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Password confirmation was incorrect." in page
    assert database.get_wom_competition_id() == 123456

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM tiles
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        assert cursor.fetchone()[0] == 1


def test_bingo_setup_reset_clears_event_data_teams_players_and_unlinks_dink_identities(
    client
):
    create_admin_user()
    login_admin(client)

    database.import_wom_competition(
        123456,
        {
            "Test Team": [
                "Test Player"
            ]
        },
        "Blackout Sky",
        {
            "test player": 987654
        },
        competition_starts_at="2026-09-05T16:00:00.000Z",
        competition_ends_at="2026-09-12T16:00:00.000Z"
    )

    tile_id = database.add_tile(
        "Reset Safety Tile",
        "KILLCOUNT",
        "Vorkath",
        "1",
        "FALSE",
        1,
        1,
        5,
        "Test tile"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT player_id
            FROM players
            WHERE lower(player_name) = lower(%s)
            ''',
            ("Test Player",)
        )
        player_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            UPDATE users
            SET player_id = %s
            WHERE lower(username) = lower(%s)
            ''',
            (
                player_id,
                "Bingo Setup Admin"
            )
        )

        cursor.execute(
            '''
            INSERT INTO dink_identities (
                dink_account_hash,
                player_id,
                observed_rsn,
                status,
                linked_at
            )
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ''',
            (
                "reset-test-hash",
                player_id,
                "Test Player",
                "LINKED"
            )
        )

        conn.commit()

    response = client.post(
        "/admin/bingo_setup",
        data={
            "action": "reset_bingo_data",
            "reset_password": "test-password",
            "reset_competition_id": "123456"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Bingo event data has been reset." in page
    assert database.get_wom_competition_id() is None

    assert database.get_team_by_name(
        "Test Team"
    ) is None

    assert database.get_player_by_name(
        "Test Player"
    ) is None

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM users
            WHERE lower(username) = lower(%s)
            ''',
            ("Bingo Setup Admin",)
        )
        assert cursor.fetchone()[0] == 1

        cursor.execute(
            '''
            SELECT player_id
            FROM users
            WHERE lower(username) = lower(%s)
            ''',
            ("Bingo Setup Admin",)
        )
        assert cursor.fetchone()[0] is None

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM tiles
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )
        assert cursor.fetchone()[0] == 0

        cursor.execute(
            '''
            SELECT
                player_id,
                observed_rsn,
                status,
                linked_at
            FROM dink_identities
            WHERE dink_account_hash = %s
            ''',
            ("reset-test-hash",)
        )

        assert cursor.fetchone() == (
            None,
            "Test Player",
            "PENDING",
            None
        )
