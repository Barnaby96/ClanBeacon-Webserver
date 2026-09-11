import io
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
from utils import database, team_photo_files


@pytest.fixture(autouse=True)
def team_data_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Team Data tests must only run against "
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


def test_team_page_requires_login(client):
    team_id = create_team(
        "LoginTeam"
    )

    create_player(
        "LoginPlayer",
        team_id
    )

    response = client.get(
        "/user/team/LoginTeam"
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_unlinked_player_account_redirects_to_account_linking(client):
    create_team(
        "UnlinkedTeam"
    )

    create_dashboard_user(
        "UnlinkedUser",
        "test-password",
        account_role="PLAYER"
    )

    login_response = login_dashboard_user(
        client,
        "UnlinkedUser",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/user/team/UnlinkedTeam"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/user/account?link_required=1"
    )


@pytest.mark.parametrize(
    "account_role",
    ["PLAYER", "ADMIN", "ORGANISER"]
)
@pytest.mark.parametrize("has_timing", [False, True])
def test_team_page_competition_countdown(
    client,
    account_role,
    has_timing
):
    team_id = create_team("CountdownTeam")
    player_id = create_player(
        "CountdownPlayer",
        team_id
    )

    create_dashboard_user(
        "CountdownUser",
        "test-password",
        account_role=account_role,
        player_id=player_id
    )

    if has_timing:
        database.import_wom_competition(
            123456,
            {},
            "Countdown Test",
            competition_starts_at=(
                "2026-09-05T16:00:00.000Z"
            ),
            competition_ends_at=(
                "2026-09-12T16:00:00.000Z"
            )
        )

    login_response = login_dashboard_user(
        client,
        "CountdownUser",
        "test-password"
    )
    assert login_response.status_code == 302

    response = client.get(
        "/user/team/CountdownTeam"
    )
    assert response.status_code == 200

    page = response.get_data(as_text=True)

    if has_timing:
        timing = database.get_wom_competition_timing()

        assert 'id="competition-countdown"' in page
        assert (
            'data-starts-at="'
            + timing["starts_at"].isoformat()
            + '"'
        ) in page
        assert (
            'data-ends-at="'
            + timing["ends_at"].isoformat()
            + '"'
        ) in page
        assert 'id="competition-countdown-value"' in page
        assert 'id="competition-countdown-deadline"' in page
    else:
        assert 'id="competition-countdown"' not in page
        assert 'data-starts-at=' not in page
        assert 'data-ends-at=' not in page


def test_player_can_only_view_own_team_and_only_link_to_own_player(
    client
):
    own_team_id = create_team(
        "OwnTeam"
    )
    other_team_id = create_team(
        "OtherTeam"
    )

    own_player_id = create_player(
        "OwnPlayer",
        own_team_id
    )

    create_player(
        "Teammate",
        own_team_id
    )

    create_player(
        "OtherPlayer",
        other_team_id
    )

    create_dashboard_user(
        "PlayerUser",
        "test-password",
        account_role="PLAYER",
        player_id=own_player_id
    )

    login_response = login_dashboard_user(
        client,
        "PlayerUser",
        "test-password"
    )

    assert login_response.status_code == 302

    own_response = client.get(
        "/user/team/OwnTeam"
    )

    assert own_response.status_code == 200

    own_html = own_response.get_data(
        as_text=True
    )

    assert "OwnTeam" in own_html
    assert 'href="/user/player/OwnPlayer"' in own_html

    assert "Teammate" in own_html
    assert 'href="/user/player/Teammate"' not in own_html

    assert "Select Team" not in own_html
    assert "Manage Team Photo" not in own_html

    other_response = client.get(
        "/user/team/OtherTeam"
    )

    assert other_response.status_code == 302
    assert other_response.headers["Location"].endswith(
        "/user/team/OwnTeam"
    )


@pytest.mark.parametrize(
    "account_role",
    [
        "ADMIN",
        "ORGANISER"
    ]
)
def test_staff_can_view_any_team_and_receive_team_controls(
    client,
    account_role
):
    first_team_id = create_team(
        "AlphaTeam"
    )
    second_team_id = create_team(
        "BetaTeam"
    )

    create_player(
        "AlphaPlayer",
        first_team_id
    )

    create_player(
        "BetaPlayer",
        second_team_id
    )

    username = f"{account_role}User"

    create_dashboard_user(
        username,
        "test-password",
        account_role=account_role
    )

    login_response = login_dashboard_user(
        client,
        username,
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/user/team/BetaTeam"
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "BetaTeam" in html
    assert "Select Team" in html
    assert "AlphaTeam" in html
    assert "Edit Team" in html
    assert 'href="/user/player/BetaPlayer"' in html

    missing_response = client.get(
        "/user/team/DoesNotExist"
    )

    assert missing_response.status_code == 404

def test_team_summary_orders_roster_and_preserves_joint_mvp():
    team_id = create_team(
        "RosterTeam",
        bingo_points=12
    )

    zebra_id = create_player(
        "Zebra",
        team_id,
        mvp_points=7
    )

    alpha_id = create_player(
        "alpha",
        team_id,
        mvp_points=7
    )

    beta_id = create_player(
        "Beta",
        team_id,
        mvp_points=2
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            UPDATE players
            SET tiles_completed = %s
            WHERE player_id = %s
            ''',
            (
                1.25,
                zebra_id
            )
        )

        cursor.execute(
            '''
            UPDATE players
            SET tiles_completed = %s
            WHERE player_id = %s
            ''',
            (
                2,
                alpha_id
            )
        )

        cursor.execute(
            '''
            UPDATE players
            SET tiles_completed = %s
            WHERE player_id = %s
            ''',
            (
                0.5,
                beta_id
            )
        )

    summary = database.get_team_data_summary(
        team_id
    )

    assert summary["team"] == {
        "team_id": team_id,
        "team_name": "RosterTeam",
        "bingo_points": 12.0
    }

    assert [
        player["player_name"]
        for player in summary["roster"]
    ] == [
        "alpha",
        "Beta",
        "Zebra"
    ]

    roster_by_name = {
        player["player_name"]: player
        for player in summary["roster"]
    }

    assert roster_by_name["alpha"]["mvp_points"] == 7.0
    assert roster_by_name["alpha"]["tile_contribution"] == 2.0

    assert roster_by_name["Beta"]["mvp_points"] == 2.0
    assert roster_by_name["Beta"]["tile_contribution"] == 0.5

    assert roster_by_name["Zebra"]["mvp_points"] == 7.0
    assert roster_by_name["Zebra"]["tile_contribution"] == 1.25

    assert summary["team_mvp"]["mvp_points"] == 7.0

    assert [
        player["player_name"]
        for player in summary["team_mvp"]["players"]
    ] == [
        "alpha",
        "Zebra"
    ]


def test_team_page_uses_exact_zero_mvp_message(client):
    team_id = create_team(
        "ZeroMvpTeam"
    )

    create_player(
        "FirstPlayer",
        team_id
    )

    create_player(
        "SecondPlayer",
        team_id
    )

    create_dashboard_user(
        "ZeroMvpAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "ZeroMvpAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/user/team/ZeroMvpTeam"
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "No MVP Points awarded yet" in html

    summary = database.get_team_data_summary(
        team_id
    )

    assert summary["team_mvp"] == {
        "mvp_points": 0,
        "players": []
    }


def test_team_summary_aggregates_genuine_relevant_drops():
    team_id = create_team(
        "DropTeam"
    )

    first_player_id = create_player(
        "DropPlayerOne",
        team_id
    )

    second_player_id = create_player(
        "DropPlayerTwo",
        team_id
    )

    tile_id = database.add_tile(
        "Burning Claw Tile",
        "ITEM",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Burning Claw Tile"
    )

    first_drop_pk = database.add_drop(
        team_id,
        first_player_id,
        "DropPlayerOne",
        "Burning claw",
        100,
        2,
        "Test source"
    )

    second_drop_pk = database.add_drop(
        team_id,
        second_player_id,
        "DropPlayerTwo",
        "Burning claw",
        100,
        3,
        "Test source"
    )

    database.add_relevant_drop(
        team_id,
        first_player_id,
        tile_id,
        "Burning Claw Tile",
        "Burning claw",
        "DropPlayerOne",
        first_drop_pk
    )

    database.add_relevant_drop(
        team_id,
        second_player_id,
        tile_id,
        "Burning Claw Tile",
        "Burning claw",
        "DropPlayerTwo",
        second_drop_pk
    )

    summary = database.get_team_data_summary(
        team_id
    )

    assert summary["relevant_drops"] == {
        "total_quantity": 5,
        "drops": [
            {
                "drop_name": "Burning claw",
                "quantity": 5
            }
        ]
    }

    assert (
        summary["stats"]["relevant_drop_quantity"]
        == 5
    )


def test_team_summary_ignores_non_relevant_and_synthetic_drops():
    team_id = create_team(
        "SyntheticDropTeam"
    )

    player_id = create_player(
        "SyntheticDropPlayer",
        team_id
    )

    tile_id = database.add_tile(
        "Synthetic Drop Tile",
        "ITEM",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Synthetic Drop Tile"
    )

    database.add_drop(
        team_id,
        player_id,
        "SyntheticDropPlayer",
        "Unrelated drop",
        100,
        7,
        "Test source"
    )

    database.add_relevant_drop(
        team_id,
        player_id,
        tile_id,
        "Synthetic Drop Tile",
        "Synthetic counter",
        "SyntheticDropPlayer",
        None
    )

    summary = database.get_team_data_summary(
        team_id
    )

    assert summary["relevant_drops"] == {
        "total_quantity": 0,
        "drops": []
    }

    assert (
        summary["stats"]["relevant_drop_quantity"]
        == 0
    )

def set_wom_metric_gain(
    competition_id,
    player_id,
    metric,
    gain
):
    with database.connect() as conn:
        cursor = conn.cursor()
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


def test_team_summary_aggregates_relevant_boss_kc_across_players():
    team_id = create_team(
        "BossTeam"
    )

    other_team_id = create_team(
        "OtherBossTeam"
    )

    first_player_id = create_player(
        "BossPlayerOne",
        team_id
    )

    second_player_id = create_player(
        "BossPlayerTwo",
        team_id
    )

    other_player_id = create_player(
        "OtherBossPlayer",
        other_team_id
    )

    first_tile_id = database.add_tile(
        "Kill Brutus 5000 times",
        "KILLCOUNT",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Kill Brutus 5000 times"
    )

    second_tile_id = database.add_tile(
        "Kill Brutus or Bryophyta 500 times",
        "KILLCOUNT",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Kill Brutus or Bryophyta 500 times"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO tile_conditions (
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            )
            VALUES
                (%s, 1, 'KILLCOUNT', 'brutus', 5000),
                (%s, 1, 'KILLCOUNT', 'brutus', 500),
                (%s, 2, 'KILLCOUNT', 'bryophyta', 500)
            ''',
            (
                first_tile_id,
                second_tile_id,
                second_tile_id
            )
        )

    competition_id = 12345
    database.set_wom_competition_id(
        competition_id
    )

    set_wom_metric_gain(
        competition_id,
        first_player_id,
        "brutus",
        108
    )

    set_wom_metric_gain(
        competition_id,
        second_player_id,
        "brutus",
        12
    )

    set_wom_metric_gain(
        competition_id,
        first_player_id,
        "bryophyta",
        0
    )

    set_wom_metric_gain(
        competition_id,
        other_player_id,
        "brutus",
        999
    )

    set_wom_metric_gain(
        99999,
        first_player_id,
        "brutus",
        500
    )

    summary = database.get_team_data_summary(
        team_id
    )

    assert summary["relevant_boss_kc"] == {
        "total_kc": 120,
        "bosses": [
            {
                "metric": "brutus",
                "kc_gained": 120,
                "related_tiles": [
                    "Kill Brutus 5000 times",
                    "Kill Brutus or Bryophyta 500 times"
                ]
            }
        ]
    }

    assert (
        summary["stats"]["relevant_boss_kc"]
        == 120
    )


def test_team_summary_aggregates_relevant_xp_across_players():
    team_id = create_team(
        "XpTeam"
    )

    other_team_id = create_team(
        "OtherXpTeam"
    )

    first_player_id = create_player(
        "XpPlayerOne",
        team_id
    )

    second_player_id = create_player(
        "XpPlayerTwo",
        team_id
    )

    other_player_id = create_player(
        "OtherXpPlayer",
        other_team_id
    )

    first_tile_id = database.add_tile(
        "Gain 1m Mining XP",
        "EXPERIENCE",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Gain 1m Mining XP"
    )

    second_tile_id = database.add_tile(
        "Gain Mining or Agility XP",
        "EXPERIENCE",
        "",
        "",
        "FALSE",
        0,
        1,
        0,
        "Gain Mining or Agility XP"
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO tile_conditions (
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            )
            VALUES
                (%s, 1, 'EXPERIENCE', 'mining', 1000000),
                (%s, 1, 'EXPERIENCE', 'mining', 500000),
                (%s, 2, 'EXPERIENCE', 'agility', 500000)
            ''',
            (
                first_tile_id,
                second_tile_id,
                second_tile_id
            )
        )

    competition_id = 54321
    database.set_wom_competition_id(
        competition_id
    )

    set_wom_metric_gain(
        competition_id,
        first_player_id,
        "mining",
        250000
    )

    set_wom_metric_gain(
        competition_id,
        second_player_id,
        "mining",
        125000
    )

    set_wom_metric_gain(
        competition_id,
        first_player_id,
        "agility",
        0
    )

    set_wom_metric_gain(
        competition_id,
        other_player_id,
        "mining",
        900000
    )

    set_wom_metric_gain(
        99999,
        first_player_id,
        "mining",
        700000
    )

    summary = database.get_team_data_summary(
        team_id
    )

    assert summary["relevant_xp"] == {
        "total_xp": 375000,
        "skills": [
            {
                "metric": "mining",
                "xp_gained": 375000,
                "related_tiles": [
                    "Gain 1m Mining XP",
                    "Gain Mining or Agility XP"
                ]
            }
        ]
    }

    assert (
        summary["stats"]["relevant_xp"]
        == 375000
    )

def get_condition_ids_by_path_and_trigger(tile_id):
    return {
        (
            int(condition[2]),
            condition[4]
        ): int(condition[0])
        for condition
        in database.get_tile_conditions(tile_id)
    }


def test_team_summary_uses_canonical_completion_path_progress():
    team_id = create_team(
        "ProgressModesTeam"
    )

    all_tile_id = database.add_tile_with_conditions(
        tile_name="ALL Progress Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "all-a",
                "target": 100
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "all-b",
                "target": 200
            }
        ]
    )

    all_conditions = get_condition_ids_by_path_and_trigger(
        all_tile_id
    )

    database.add_tile_condition_progress(
        team_id,
        all_conditions[(1, "all-a")],
        50
    )

    database.add_tile_condition_progress(
        team_id,
        all_conditions[(1, "all-b")],
        50
    )

    sum_tile_id = database.add_tile_with_conditions(
        tile_name="SUM Progress Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "sum-a",
                "target": 100
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "sum-b",
                "target": 100
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "SUM",
                "route_target": 100,
                "require_unique": False
            }
        ]
    )

    sum_conditions = get_condition_ids_by_path_and_trigger(
        sum_tile_id
    )

    database.add_tile_condition_progress(
        team_id,
        sum_conditions[(1, "sum-a")],
        20
    )

    database.add_tile_condition_progress(
        team_id,
        sum_conditions[(1, "sum-b")],
        30
    )

    unique_tile_id = database.add_tile_with_conditions(
        tile_name="Unique N Of Progress Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "unique-a",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "unique-b",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "unique-c",
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

    unique_conditions = get_condition_ids_by_path_and_trigger(
        unique_tile_id
    )

    database.add_tile_condition_progress(
        team_id,
        unique_conditions[(1, "unique-a")],
        5
    )

    non_unique_tile_id = database.add_tile_with_conditions(
        tile_name="Non Unique N Of Progress Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "non-unique-a",
                "target": 10
            },
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": "non-unique-b",
                "target": 10
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 4,
                "require_unique": False
            }
        ]
    )

    non_unique_conditions = (
        get_condition_ids_by_path_and_trigger(
            non_unique_tile_id
        )
    )

    database.add_tile_condition_progress(
        team_id,
        non_unique_conditions[
            (1, "non-unique-a")
        ],
        3
    )

    alternative_tile_id = (
        database.add_tile_with_conditions(
            tile_name="Alternative Path Progress Tile",
            tile_points=1,
            tile_rules="",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "MANUAL",
                    "condition_trigger": "alternative-all",
                    "target": 100
                },
                {
                    "completion_path": 2,
                    "condition_type": "MANUAL",
                    "condition_trigger": "alternative-sum-a",
                    "target": 100
                },
                {
                    "completion_path": 2,
                    "condition_type": "MANUAL",
                    "condition_trigger": "alternative-sum-b",
                    "target": 100
                }
            ],
            completion_paths=[
                {
                    "completion_path": 1,
                    "route_mode": "ALL",
                    "route_target": None,
                    "require_unique": False
                },
                {
                    "completion_path": 2,
                    "route_mode": "SUM",
                    "route_target": 100,
                    "require_unique": False
                }
            ]
        )
    )

    alternative_conditions = (
        get_condition_ids_by_path_and_trigger(
            alternative_tile_id
        )
    )

    database.add_tile_condition_progress(
        team_id,
        alternative_conditions[
            (1, "alternative-all")
        ],
        25
    )

    database.add_tile_condition_progress(
        team_id,
        alternative_conditions[
            (2, "alternative-sum-a")
        ],
        30
    )

    database.add_tile_condition_progress(
        team_id,
        alternative_conditions[
            (2, "alternative-sum-b")
        ],
        50
    )

    summary = database.get_team_data_summary(
        team_id
    )

    progress_by_name = {
        tile["tile_name"]: tile
        for tile in summary["tiles_in_progress"]
    }

    assert (
        progress_by_name["ALL Progress Tile"][
            "progress_fraction"
        ]
        == 0.375
    )

    assert (
        progress_by_name["ALL Progress Tile"][
            "progress_percentage"
        ]
        == 37.5
    )

    assert (
        progress_by_name["SUM Progress Tile"][
            "progress_percentage"
        ]
        == 50.0
    )

    assert (
        progress_by_name[
            "Unique N Of Progress Tile"
        ]["progress_percentage"]
        == 50.0
    )

    assert (
        progress_by_name[
            "Non Unique N Of Progress Tile"
        ]["progress_percentage"]
        == 75.0
    )

    assert (
        progress_by_name[
            "Alternative Path Progress Tile"
        ]["progress_percentage"]
        == 80.0
    )


def test_team_summary_filters_and_sorts_tiles_in_progress():
    team_id = create_team(
        "ProgressSortTeam"
    )

    tile_specs = [
        (
            "Top Percent",
            1,
            75
        ),
        (
            "High Points Fifty",
            10,
            50
        ),
        (
            "Zulu Fifty",
            5,
            50
        ),
        (
            "Alpha Fifty",
            5,
            50
        ),
        (
            "Zero Progress",
            100,
            0
        ),
        (
            "Completed Progress",
            100,
            90
        )
    ]

    tile_ids = {}

    for (
        tile_name,
        tile_points,
        progress
    ) in tile_specs:
        tile_id = database.add_tile_with_conditions(
            tile_name=tile_name,
            tile_points=tile_points,
            tile_rules="",
            conditions=[
                {
                    "completion_path": 1,
                    "condition_type": "MANUAL",
                    "condition_trigger":
                        f"{tile_name}-trigger",
                    "target": 100
                }
            ]
        )

        tile_ids[tile_name] = tile_id

        if progress > 0:
            conditions = (
                get_condition_ids_by_path_and_trigger(
                    tile_id
                )
            )

            database.add_tile_condition_progress(
                team_id,
                conditions[
                    (
                        1,
                        f"{tile_name}-trigger"
                    )
                ],
                progress
            )

    database.add_completed_tile(
        tile_ids["Completed Progress"],
        team_id
    )

    summary = database.get_team_data_summary(
        team_id
    )

    assert [
        tile["tile_name"]
        for tile in summary["tiles_in_progress"]
    ] == [
        "Top Percent",
        "High Points Fifty",
        "Alpha Fifty",
        "Zulu Fifty"
    ]

    progress_names = {
        tile["tile_name"]
        for tile in summary["tiles_in_progress"]
    }

    assert "Zero Progress" not in progress_names
    assert "Completed Progress" not in progress_names


def test_team_summary_counts_and_orders_completed_tiles_newest_first():
    team_id = create_team(
        "CompletedTeam"
    )

    older_tile_id = database.add_tile(
        "Older Completed Tile",
        "MANUAL",
        "",
        "",
        "FALSE",
        0,
        1,
        3,
        ""
    )

    newer_tile_id = database.add_tile(
        "Newer Completed Tile",
        "MANUAL",
        "",
        "",
        "FALSE",
        0,
        1,
        7,
        ""
    )

    database.add_completed_tile(
        older_tile_id,
        team_id
    )

    database.add_completed_tile(
        newer_tile_id,
        team_id
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            UPDATE completed_tiles
            SET completed_at = %s::TIMESTAMPTZ
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                "2026-09-07T18:15:00+00:00",
                team_id,
                older_tile_id
            )
        )

        cursor.execute(
            '''
            UPDATE completed_tiles
            SET completed_at = %s::TIMESTAMPTZ
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                "2026-09-08T19:31:00+00:00",
                team_id,
                newer_tile_id
            )
        )

    summary = database.get_team_data_summary(
        team_id
    )

    assert (
        summary["stats"]["tiles_completed"]
        == 2
    )

    assert [
        tile["tile_name"]
        for tile in summary["completed_tiles"]
    ] == [
        "Newer Completed Tile",
        "Older Completed Tile"
    ]

    assert [
        tile["tile_points"]
        for tile in summary["completed_tiles"]
    ] == [
        7.0,
        3.0
    ]

    assert (
        summary["completed_tiles"][0][
            "completed_at"
        ]
        > summary["completed_tiles"][1][
            "completed_at"
        ]
    )


def test_team_page_emits_timezone_aware_completed_tile_datetimes(
    client
):
    team_id = create_team(
        "TimestampTeam"
    )

    tile_id = database.add_tile(
        "Timestamp Completed Tile",
        "MANUAL",
        "",
        "",
        "FALSE",
        0,
        1,
        4,
        ""
    )

    database.add_completed_tile(
        tile_id,
        team_id
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            UPDATE completed_tiles
            SET completed_at = %s::TIMESTAMPTZ
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                "2026-09-08T19:31:00+00:00",
                team_id,
                tile_id
            )
        )

    summary = database.get_team_data_summary(
        team_id
    )

    completed_at = summary[
        "completed_tiles"
    ][0]["completed_at"]

    assert completed_at.tzinfo is not None
    assert completed_at.utcoffset() is not None

    create_dashboard_user(
        "TimestampAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "TimestampAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/user/team/TimestampTeam"
    )

    assert response.status_code == 200

    html = response.get_data(
        as_text=True
    )

    assert "Timestamp Completed Tile" in html
    assert 'class="osrs-local-datetime"' in html
    assert (
        f'datetime="{completed_at.isoformat()}"'
        in html
    )


@pytest.mark.parametrize(
    (
        "filename",
        "file_bytes"
    ),
    [
        (
            "team-photo.png",
            b"\x89PNG\r\n\x1a\n"
            b"test-png-data"
        ),
        (
            "team-photo.jpg",
            b"\xff\xd8\xff"
            b"test-jpeg-data"
        ),
        (
            "team-photo.jpeg",
            b"\xff\xd8\xff"
            b"test-jpeg-data"
        ),
        (
            "team-photo.webp",
            b"RIFF"
            b"\x04\x00\x00\x00"
            b"WEBP"
            b"test-webp-data"
        )
    ]
)
def test_team_photo_file_save_resolve_delete_lifecycle(
    filename,
    file_bytes
):
    saved_path = None

    try:
        saved_path = (
            team_photo_files.save_team_photo_file(
                file_bytes,
                filename
            )
        )

        assert saved_path.startswith(
            os.path.join(
                "uploads",
                "team_photos",
                "team_photo_"
            )
        )

        absolute_path = (
            team_photo_files.resolve_team_photo_path(
                saved_path
            )
        )

        assert absolute_path is not None
        assert os.path.isfile(
            absolute_path
        )

        with open(
            absolute_path,
            "rb"
        ) as photo_file:
            assert photo_file.read() == file_bytes

        assert (
            team_photo_files.delete_team_photo_file(
                saved_path
            )
            is True
        )

        assert (
            team_photo_files.resolve_team_photo_path(
                saved_path
            )
            is None
        )

        saved_path = None

    finally:
        if saved_path is not None:
            team_photo_files.delete_team_photo_file(
                saved_path
            )


@pytest.mark.parametrize(
    (
        "file_bytes",
        "filename",
        "expected_message"
    ),
    [
        (
            b"",
            "empty.png",
            "Team photo is empty."
        ),
        (
            b"\x89PNG\r\n\x1a\nimage-data",
            "photo.gif",
            (
                "Team photo must be a PNG, JPG, JPEG, "
                "or WebP image."
            )
        ),
        (
            b"not-an-image",
            "photo.png",
            (
                "Team photo is not a recognised PNG, JPG, "
                "JPEG, or WebP image."
            )
        ),
        (
            b"\x89PNG\r\n\x1a\nimage-data",
            "photo.jpg",
            (
                "Team photo file extension does not match "
                "the image format."
            )
        )
    ]
)
def test_team_photo_file_rejects_invalid_uploads(
    file_bytes,
    filename,
    expected_message
):
    with pytest.raises(
        ValueError,
        match=expected_message.replace(
            ".",
            r"\."
        )
    ):
        team_photo_files.save_team_photo_file(
            file_bytes,
            filename
        )


def test_team_photo_file_rejects_oversize_upload():
    oversized_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + (
            b"x"
            * team_photo_files.MAX_TEAM_PHOTO_BYTES
        )
    )

    with pytest.raises(
        ValueError,
        match=r"Team photo must be 10 MB or smaller\."
    ):
        team_photo_files.save_team_photo_file(
            oversized_bytes,
            "oversized.png"
        )


def test_team_photo_resolver_rejects_unsafe_paths():
    assert (
        team_photo_files.resolve_team_photo_path(
            "../../outside.png"
        )
        is None
    )

    assert (
        team_photo_files.resolve_team_photo_path(
            os.path.join(
                "uploads",
                "team_photos",
                "not_a_team_photo.png"
            )
        )
        is None
    )

    assert (
        team_photo_files.resolve_team_photo_path(
            os.path.join(
                "uploads",
                "team_photos",
                "team_photo_not-a-uuid.png"
            )
        )
        is None
    )

    assert (
        team_photo_files.resolve_team_photo_path(
            os.path.join(
                "uploads",
                "team_photos",
                (
                    "team_photo_"
                    "00000000000000000000000000000000"
                    ".gif"
                )
            )
        )
        is None
    )


def test_edit_team_route_uploads_team_photo(client):
    team_id = create_team(
        "PhotoUploadTeam"
    )

    create_dashboard_user(
        "PhotoUploadAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "PhotoUploadAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    photo_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"route-upload-test"
    )

    saved_path = None

    try:
        response = client.post(
            f"/team/teams/edit/{team_id}",
            data={
                "team_name": "PhotoUploadTeam",
                "team_points": "0",
                "team_webhook": "",
                "discord_role_id": "",
                "team_photo": (
                    io.BytesIO(photo_bytes),
                    "team-photo.png"
                )
            },
            content_type="multipart/form-data"
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith(
            "/user/team/PhotoUploadTeam"
        )

        team = database.get_team_by_id(
            team_id
        )

        saved_path = team[5]

        assert saved_path is not None

        absolute_path = (
            team_photo_files.resolve_team_photo_path(
                saved_path
            )
        )

        assert absolute_path is not None

        with open(
            absolute_path,
            "rb"
        ) as photo_file:
            assert photo_file.read() == photo_bytes

    finally:
        if saved_path is not None:
            team_photo_files.delete_team_photo_file(
                saved_path
            )


def test_edit_team_route_replaces_existing_team_photo(
    client
):
    team_id = create_team(
        "PhotoReplaceTeam"
    )

    old_path = (
        team_photo_files.save_team_photo_file(
            (
                b"\x89PNG\r\n\x1a\n"
                b"old-photo"
            ),
            "old-photo.png"
        )
    )

    database.set_team_photo_path(
        team_id,
        old_path
    )

    create_dashboard_user(
        "PhotoReplaceAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "PhotoReplaceAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    new_path = None

    try:
        response = client.post(
            f"/team/teams/edit/{team_id}",
            data={
                "team_name": "PhotoReplaceTeam",
                "team_points": "0",
                "team_webhook": "",
                "discord_role_id": "",
                "team_photo": (
                    io.BytesIO(
                        b"\xff\xd8\xff"
                        b"new-photo"
                    ),
                    "new-photo.jpg"
                )
            },
            content_type="multipart/form-data"
        )

        assert response.status_code == 302

        team = database.get_team_by_id(
            team_id
        )

        new_path = team[5]

        assert new_path is not None
        assert new_path != old_path

        assert (
            team_photo_files.resolve_team_photo_path(
                old_path
            )
            is None
        )

        assert (
            team_photo_files.resolve_team_photo_path(
                new_path
            )
            is not None
        )

    finally:
        team_photo_files.delete_team_photo_file(
            old_path
        )

        if new_path is not None:
            team_photo_files.delete_team_photo_file(
                new_path
            )


def test_edit_team_route_removes_existing_team_photo(
    client
):
    team_id = create_team(
        "PhotoRemoveTeam"
    )

    old_path = (
        team_photo_files.save_team_photo_file(
            (
                b"\x89PNG\r\n\x1a\n"
                b"remove-photo"
            ),
            "remove-photo.png"
        )
    )

    database.set_team_photo_path(
        team_id,
        old_path
    )

    create_dashboard_user(
        "PhotoRemoveAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "PhotoRemoveAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    try:
        response = client.post(
            (
                f"/team/teams/edit/{team_id}"
                "/photo/remove"
            )
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith(
            f"/team/teams/edit/{team_id}"
        )

        team = database.get_team_by_id(
            team_id
        )

        assert team[5] is None

        assert (
            team_photo_files.resolve_team_photo_path(
                old_path
            )
            is None
        )

    finally:
        team_photo_files.delete_team_photo_file(
            old_path
        )


def test_edit_team_route_ignores_legacy_remove_flag_when_uploading_photo(
    client
):
    team_id = create_team(
        "PhotoConflictTeam"
    )

    old_path = (
        team_photo_files.save_team_photo_file(
            (
                b"\x89PNG\r\n\x1a\n"
                b"existing-photo"
            ),
            "existing-photo.png"
        )
    )

    database.set_team_photo_path(
        team_id,
        old_path
    )

    create_dashboard_user(
        "PhotoConflictAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "PhotoConflictAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    new_path = None

    try:
        response = client.post(
            f"/team/teams/edit/{team_id}",
            data={
                "team_name": "PhotoConflictTeam",
                "remove_team_photo": "1",
                "team_photo": (
                    io.BytesIO(
                        b"\x89PNG\r\n\x1a\n"
                        b"replacement-photo"
                    ),
                    "replacement-photo.png"
                )
            },
            content_type="multipart/form-data"
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith(
            "/user/team/PhotoConflictTeam"
        )

        team = database.get_team_by_id(
            team_id
        )

        new_path = team[5]

        assert new_path is not None
        assert new_path != old_path

        assert (
            team_photo_files.resolve_team_photo_path(
                old_path
            )
            is None
        )

        assert (
            team_photo_files.resolve_team_photo_path(
                new_path
            )
            is not None
        )

    finally:
        team_photo_files.delete_team_photo_file(
            old_path
        )

        if new_path is not None:
            team_photo_files.delete_team_photo_file(
                new_path
            )


def test_team_photo_route_returns_404_when_team_has_no_photo(
    client
):
    team_id = create_team(
        "NoPhotoTeam"
    )

    create_dashboard_user(
        "NoPhotoAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "NoPhotoAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        f"/user/team/{team_id}/photo"
    )

    assert response.status_code == 404


def test_player_can_only_view_own_team_photo(
    client
):
    own_team_id = create_team(
        "OwnPhotoTeam"
    )

    other_team_id = create_team(
        "OtherPhotoTeam"
    )

    own_player_id = create_player(
        "OwnPhotoPlayer",
        own_team_id
    )

    create_player(
        "OtherPhotoPlayer",
        other_team_id
    )

    own_photo_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"own-team-photo"
    )

    other_photo_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"other-team-photo"
    )

    own_photo_path = (
        team_photo_files.save_team_photo_file(
            own_photo_bytes,
            "own-team-photo.png"
        )
    )

    other_photo_path = (
        team_photo_files.save_team_photo_file(
            other_photo_bytes,
            "other-team-photo.png"
        )
    )

    database.set_team_photo_path(
        own_team_id,
        own_photo_path
    )

    database.set_team_photo_path(
        other_team_id,
        other_photo_path
    )

    create_dashboard_user(
        "OwnPhotoUser",
        "test-password",
        account_role="PLAYER",
        player_id=own_player_id
    )

    login_response = login_dashboard_user(
        client,
        "OwnPhotoUser",
        "test-password"
    )

    assert login_response.status_code == 302

    try:
        own_response = client.get(
            f"/user/team/{own_team_id}/photo"
        )

        assert own_response.status_code == 200
        assert own_response.data == own_photo_bytes
        own_response.close()

        other_response = client.get(
            f"/user/team/{other_team_id}/photo"
        )

        assert other_response.status_code == 404

    finally:
        team_photo_files.delete_team_photo_file(
            own_photo_path
        )

        team_photo_files.delete_team_photo_file(
            other_photo_path
        )


@pytest.mark.parametrize(
    "account_role",
    [
        "ADMIN",
        "ORGANISER"
    ]
)
def test_staff_can_view_any_team_photo(
    client,
    account_role
):
    team_id = create_team(
        f"{account_role}PhotoTeam"
    )

    photo_bytes = (
        b"\xff\xd8\xff"
        b"staff-visible-photo"
    )

    photo_path = (
        team_photo_files.save_team_photo_file(
            photo_bytes,
            "staff-visible-photo.jpg"
        )
    )

    database.set_team_photo_path(
        team_id,
        photo_path
    )

    username = f"{account_role}PhotoUser"

    create_dashboard_user(
        username,
        "test-password",
        account_role=account_role
    )

    login_response = login_dashboard_user(
        client,
        username,
        "test-password"
    )

    assert login_response.status_code == 302

    try:
        response = client.get(
            f"/user/team/{team_id}/photo"
        )

        assert response.status_code == 200
        assert response.data == photo_bytes
        response.close()

    finally:
        team_photo_files.delete_team_photo_file(
            photo_path
        )


def test_team_photo_route_rejects_invalid_stored_path(
    client
):
    team_id = create_team(
        "UnsafePhotoTeam"
    )

    database.set_team_photo_path(
        team_id,
        "../../outside.png"
    )

    create_dashboard_user(
        "UnsafePhotoAdmin",
        "test-password",
        account_role="ADMIN"
    )

    login_response = login_dashboard_user(
        client,
        "UnsafePhotoAdmin",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        f"/user/team/{team_id}/photo"
    )

    assert response.status_code == 404