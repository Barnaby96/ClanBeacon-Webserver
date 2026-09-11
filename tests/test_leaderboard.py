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
def leaderboard_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Leaderboard tests must only run against "
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


def create_dashboard_user(
    username,
    password,
    *,
    account_role="PLAYER",
    player_id=None
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
                account_role = %s,
                player_id = %s
            WHERE LOWER(BTRIM(username))
                = LOWER(BTRIM(%s))
            ''',
            (
                account_role,
                player_id,
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
    bingo_points=0
):
    database.add_team(
        team_name,
        bingo_points,
        None
    )

    team = database.get_team_by_name(
        team_name
    )

    return team[3]


def create_player(
    player_name,
    team_id,
    mvp_points=0
):
    database.add_player(
        player_name,
        0,
        0,
        0,
        team_id,
        0
    )

    player = database.get_player_by_name(
        player_name
    )

    if mvp_points:
        database.add_player_points(
            player[0],
            mvp_points
        )

    return player[0]


def add_completed_test_tile(
    team_id,
    tile_name
):
    tile_id = database.add_tile(
        tile_name,
        "KILLCOUNT",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        tile_name
    )

    database.add_completed_tile(
        tile_id,
        team_id
    )

    return tile_id


def test_leaderboard_ranks_by_points_then_tiles_and_preserves_mvp_ties():
    alpha_id = create_team(
        "Alpha",
        bingo_points=10
    )
    beta_id = create_team(
        "Beta",
        bingo_points=10
    )
    delta_id = create_team(
        "Delta",
        bingo_points=10
    )
    gamma_id = create_team(
        "Gamma",
        bingo_points=5
    )

    create_player(
        "Alpha Player",
        alpha_id
    )

    create_player(
        "Beta One",
        beta_id,
        mvp_points=6
    )
    create_player(
        "Beta Two",
        beta_id,
        mvp_points=6
    )

    create_player(
        "Delta One",
        delta_id,
        mvp_points=6
    )
    create_player(
        "Delta Two",
        delta_id,
        mvp_points=2
    )

    create_player(
        "Gamma Player",
        gamma_id
    )

    add_completed_test_tile(
        alpha_id,
        "Alpha Tile"
    )

    for number in range(1, 3):
        add_completed_test_tile(
            beta_id,
            f"Beta Tile {number}"
        )

    for number in range(1, 3):
        add_completed_test_tile(
            delta_id,
            f"Delta Tile {number}"
        )

    for number in range(1, 4):
        add_completed_test_tile(
            gamma_id,
            f"Gamma Tile {number}"
        )

    result = database.get_leaderboard_summary()

    assert [
        team["team_name"]
        for team in result["teams"]
    ] == [
        "Beta",
        "Delta",
        "Alpha",
        "Gamma"
    ]

    assert [
        team["rank"]
        for team in result["teams"]
    ] == [
        1,
        1,
        3,
        4
    ]

    beta = result["teams"][0]
    delta = result["teams"][1]
    alpha = result["teams"][2]
    gamma = result["teams"][3]

    assert beta["bingo_points"] == 10.0
    assert beta["tiles_completed"] == 2
    assert beta["mvp_points"] == 6.0
    assert [
        player["player_name"]
        for player in beta["mvp_players"]
    ] == [
        "Beta One",
        "Beta Two"
    ]

    assert delta["bingo_points"] == 10.0
    assert delta["tiles_completed"] == 2
    assert delta["mvp_points"] == 6.0
    assert [
        player["player_name"]
        for player in delta["mvp_players"]
    ] == [
        "Delta One"
    ]

    assert alpha["bingo_points"] == 10.0
    assert alpha["tiles_completed"] == 1
    assert alpha["mvp_points"] == 0.0
    assert alpha["mvp_players"] == []

    assert gamma["bingo_points"] == 5.0
    assert gamma["tiles_completed"] == 3

    assert result["clan"]["completed_tiles"] == 8
    assert result["clan"]["team_count"] == 4
    assert result["clan"]["team_names"] == [
        "Alpha",
        "Beta",
        "Delta",
        "Gamma"
    ]

    assert result["clan"]["mvp_points"] == 6.0
    assert [
        player["player_name"]
        for player in result["clan"]["mvp_players"]
    ] == [
        "Beta One",
        "Beta Two",
        "Delta One"
    ]


def test_leaderboard_clan_totals_use_current_relevant_competition_data():
    team_id = create_team(
        "Clan Totals Team"
    )

    first_player_id = create_player(
        "Clan Totals One",
        team_id
    )
    second_player_id = create_player(
        "Clan Totals Two",
        team_id
    )

    first_kc_tile = database.add_tile_with_conditions(
        tile_name="Clan KC One",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "KILLCOUNT",
                "condition_trigger": "brutus",
                "target": 500
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None
            }
        ]
    )

    database.add_tile_with_conditions(
        tile_name="Clan KC Duplicate",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "KILLCOUNT",
                "condition_trigger": "Brutus",
                "target": 500
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None
            }
        ]
    )

    database.add_tile_with_conditions(
        tile_name="Clan XP One",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "EXPERIENCE",
                "condition_trigger": "agility",
                "target": 100000
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None
            }
        ]
    )

    database.add_tile_with_conditions(
        tile_name="Clan XP Duplicate",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "EXPERIENCE",
                "condition_trigger": "Agility",
                "target": 100000
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "ALL",
                "route_target": None
            }
        ]
    )

    competition_id = 424242
    database.set_wom_competition_id(
        competition_id
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        for (
            player_id,
            metric,
            gain
        ) in [
            (
                first_player_id,
                "brutus",
                100
            ),
            (
                second_player_id,
                "Brutus",
                50
            ),
            (
                first_player_id,
                "agility",
                1000
            ),
            (
                second_player_id,
                "Agility",
                2500
            ),
            (
                first_player_id,
                "irrelevant_metric",
                999999
            )
        ]:
            cursor.execute(
                '''
                INSERT INTO wom_metric_state (
                    competition_id,
                    player_id,
                    metric,
                    last_processed_gain
                )
                VALUES (%s, %s, %s, %s)
                ''',
                (
                    competition_id,
                    player_id,
                    metric,
                    gain
                )
            )

    drop_pk = database.add_drop(
        team_id,
        first_player_id,
        "Clan Totals One",
        "Burning claw",
        100,
        5,
        "Test source"
    )

    database.add_relevant_drop(
        team_id,
        first_player_id,
        first_kc_tile,
        "Clan KC One",
        "Burning claw",
        "Clan Totals One",
        drop_pk
    )

    database.add_relevant_drop(
        team_id,
        first_player_id,
        first_kc_tile,
        "Clan KC One",
        "Synthetic counter",
        "Clan Totals One",
        None
    )

    result = database.get_leaderboard_summary()

    assert result["competition_id"] == competition_id
    assert result["clan"]["relevant_boss_kc"] == 150
    assert result["clan"]["relevant_xp"] == 3500
    assert result["clan"]["relevant_drop_quantity"] == 5


def test_leaderboard_player_links_only_own_player_and_team(
    client
):
    own_team_id = create_team(
        "OwnTeam",
        bingo_points=5
    )
    other_team_id = create_team(
        "OtherTeam",
        bingo_points=10
    )

    own_player_id = create_player(
        "OwnPlayer",
        own_team_id,
        mvp_points=5
    )
    create_player(
        "OtherPlayer",
        other_team_id,
        mvp_points=8
    )

    database.set_wom_competition_id(
        123456
    )

    create_dashboard_user(
        "LeaderboardPlayer",
        "test-password",
        account_role="PLAYER",
        player_id=own_player_id
    )

    login_response = login_dashboard_user(
        client,
        "LeaderboardPlayer",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/user/leaderboard"
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert 'href="/user/team/OwnTeam"' in html
    assert 'href="/user/player/OwnPlayer"' in html

    assert "OtherTeam" in html
    assert "OtherPlayer" in html

    assert 'href="/user/team/OtherTeam"' not in html
    assert 'href="/user/player/OtherPlayer"' not in html

    assert (
        'href="https://wiseoldman.net/competitions/123456"'
        in html
    )
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html


@pytest.mark.parametrize(
    "account_role",
    [
        "ADMIN",
        "ORGANISER"
    ]
)
def test_leaderboard_staff_can_link_all_players_and_teams(
    client,
    account_role
):
    first_team_id = create_team(
        "FirstTeam",
        bingo_points=5
    )
    second_team_id = create_team(
        "SecondTeam",
        bingo_points=10
    )

    create_player(
        "FirstPlayer",
        first_team_id,
        mvp_points=5
    )
    create_player(
        "SecondPlayer",
        second_team_id,
        mvp_points=8
    )

    create_dashboard_user(
        f"Leaderboard{account_role}",
        "test-password",
        account_role=account_role
    )

    login_response = login_dashboard_user(
        client,
        f"Leaderboard{account_role}",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/user/leaderboard"
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert 'href="/user/team/FirstTeam"' in html
    assert 'href="/user/team/SecondTeam"' in html

    assert 'href="/user/player/FirstPlayer"' in html
    assert 'href="/user/player/SecondPlayer"' in html