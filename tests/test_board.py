import os

import pytest

from utils import database, db_entities
from main import create_app


@pytest.fixture(autouse=True)
def board_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Board regression tests must only run against "
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


def create_admin_user():
    database.add_user(
        "Board Test Admin",
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
            ("Board Test Admin",)
        )


def login_admin(client):
    create_admin_user()

    response = client.post(
        "/login",
        data={
            "username": "Board Test Admin",
            "password": "test-password"
        }
    )

    assert response.status_code == 302


def create_board_user(
    username,
    *,
    account_role="PLAYER",
    player_id=None
):
    database.add_user(
        username,
        "test-password"
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


def login_board_user(
    client,
    username
):
    response = client.post(
        "/login",
        data={
            "username": username,
            "password": "test-password"
        }
    )

    assert response.status_code == 302


def create_board_team_and_player(
    team_name,
    player_name
):
    database.add_team(
        team_name,
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            team_name
        )
    )

    database.add_player(
        player_name,
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            player_name
        )
    )

    return team, player


def create_test_tile(tile_name):
    return database.add_tile(
        tile_name,
        "NICHE",
        "",
        "",
        "FALSE",
        0,
        1,
        1,
        "Board regression test tile"
    )


def test_set_tile_board_coordinate_assigns_empty_coordinate():
    tile_id = create_test_tile(
        "Board Tile One"
    )

    tile = db_entities.Tile(
        database.get_tile_by_id(tile_id)
    )

    assert tile.board_coordinate is None

    database.set_tile_board_coordinate(
        tile_id,
        "C4"
    )

    updated_tile = db_entities.Tile(
        database.get_tile_by_id(tile_id)
    )

    assert updated_tile.board_coordinate == "C4"


def test_set_tile_board_coordinate_swaps_occupied_coordinates():
    first_tile_id = create_test_tile(
        "Board Tile One"
    )
    second_tile_id = create_test_tile(
        "Board Tile Two"
    )

    database.set_tile_board_coordinate(
        first_tile_id,
        "B2"
    )
    database.set_tile_board_coordinate(
        second_tile_id,
        "D5"
    )

    database.set_tile_board_coordinate(
        first_tile_id,
        "D5"
    )

    first_tile = db_entities.Tile(
        database.get_tile_by_id(first_tile_id)
    )
    second_tile = db_entities.Tile(
        database.get_tile_by_id(second_tile_id)
    )

    assert first_tile.board_coordinate == "D5"
    assert second_tile.board_coordinate == "B2"


def test_set_tile_board_coordinate_displaces_to_unassigned():
    assigned_tile_id = create_test_tile(
        "Assigned Board Tile"
    )
    unassigned_tile_id = create_test_tile(
        "Unassigned Board Tile"
    )

    database.set_tile_board_coordinate(
        assigned_tile_id,
        "C3"
    )

    database.set_tile_board_coordinate(
        unassigned_tile_id,
        "C3"
    )

    assigned_tile = db_entities.Tile(
        database.get_tile_by_id(assigned_tile_id)
    )
    unassigned_tile = db_entities.Tile(
        database.get_tile_by_id(unassigned_tile_id)
    )

    assert assigned_tile.board_coordinate is None
    assert unassigned_tile.board_coordinate == "C3"


def test_set_tile_board_coordinate_can_be_unassigned():
    tile_id = create_test_tile(
        "Board Tile To Unassign"
    )

    database.set_tile_board_coordinate(
        tile_id,
        "E5"
    )

    database.set_tile_board_coordinate(
        tile_id,
        None
    )

    tile = db_entities.Tile(
        database.get_tile_by_id(tile_id)
    )

    assert tile.board_coordinate is None


def test_set_tile_board_coordinate_rejects_invalid_coordinate():
    tile_id = create_test_tile(
        "Board Tile Invalid Coordinate"
    )

    database.set_tile_board_coordinate(
        tile_id,
        "B4"
    )

    with pytest.raises(
        ValueError,
        match="Board coordinate must be between A1 and E5."
    ):
        database.set_tile_board_coordinate(
            tile_id,
            "F1"
        )

    tile = db_entities.Tile(
        database.get_tile_by_id(tile_id)
    )

    assert tile.board_coordinate == "B4"


def test_set_tile_board_coordinate_rejects_missing_tile():
    with pytest.raises(
        ValueError,
        match="Tile 999 does not exist."
    ):
        database.set_tile_board_coordinate(
            999,
            "A1"
        )


def test_board_position_route_updates_coordinate(client):
    tile_id = create_test_tile(
        "Board Route Tile"
    )

    login_admin(client)

    response = client.post(
        f"/tile/tiles/board-position/{tile_id}",
        data={
            "board_coordinate": "D2"
        }
    )

    assert response.status_code == 302

    tile = db_entities.Tile(
        database.get_tile_by_id(tile_id)
    )

    assert tile.board_coordinate == "D2"


def test_board_position_route_rejects_invalid_coordinate(client):
    tile_id = create_test_tile(
        "Board Route Invalid Coordinate"
    )

    database.set_tile_board_coordinate(
        tile_id,
        "A3"
    )

    login_admin(client)

    response = client.post(
        f"/tile/tiles/board-position/{tile_id}",
        data={
            "board_coordinate": "G7"
        }
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/tile/tiles/edit/{tile_id}"
    )

    tile = db_entities.Tile(
        database.get_tile_by_id(tile_id)
    )

    assert tile.board_coordinate == "A3"


def test_edit_tile_renders_current_board_position(client):
    tile_id = create_test_tile(
        "Board Position Form Tile"
    )

    database.set_tile_board_coordinate(
        tile_id,
        "C4"
    )

    login_admin(client)

    response = client.get(
        f"/tile/tiles/edit/{tile_id}"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert "Board Position" in page_html
    assert 'name="board_coordinate"' in page_html
    assert "Save Board Position" in page_html

    coordinate_position = page_html.index(
        'value="C4"'
    )

    option_end = page_html.index(
        "</option>",
        coordinate_position
    )

    coordinate_option = page_html[
        coordinate_position:option_end
    ]

    assert "selected" in coordinate_option


def test_board_position_route_works_after_recorded_activity(client):
    tile_id = create_test_tile(
        "Board Activity Tile"
    )

    database.add_team(
        "Board Activity Team",
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Board Activity Team"
        )
    )

    database.add_completed_tile(
        tile_id,
        team.team_id
    )

    with pytest.raises(
        ValueError,
        match=(
            "This tile cannot be edited because progress "
            "or evidence has already been recorded for it."
        )
    ):
        database.update_tile_with_conditions(
            tile_id,
            "Board Activity Tile",
            1,
            "Board regression test tile",
            [
                {
                    "completion_path": 1,
                    "condition_type": "MANUAL",
                    "condition_trigger": None,
                    "target": 1
                }
            ]
        )

    login_admin(client)

    response = client.post(
        f"/tile/tiles/board-position/{tile_id}",
        data={
            "board_coordinate": "E4"
        }
    )

    assert response.status_code == 302

    tile = db_entities.Tile(
        database.get_tile_by_id(tile_id)
    )

    assert tile.board_coordinate == "E4"


def test_board_renders_all_25_coordinates_with_empty_cells(client):
    tile_id = database.add_tile_with_conditions(
        "Board Render Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    database.set_tile_board_coordinate(
        tile_id,
        "D4"
    )

    database.add_team(
        "Board Render Team",
        0,
        None
    )

    login_admin(client)
    response = client.get(
        "/board/Board Render Team"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert "Board Render Tile" in page_html
    assert 'class="osrs-bingo-scroll"' in page_html
    assert "min-width: 620px;" in page_html
    scroll_wrapper_position = page_html.index(
        'class="osrs-bingo-scroll"'
    )
    frame_position = page_html.index(
        'class="osrs-bingo-frame"'
    )
    first_wrapper_close = page_html.index(
        "</div>",
        scroll_wrapper_position
    )

    assert (
        scroll_wrapper_position
        < frame_position
        < first_wrapper_close
    )

    assert ">D4<" in page_html.replace(
        "\n",
        ""
    ).replace(
        " ",
        ""
    )

    assert (
        'aria-label="Empty bingo tile D4"'
        not in page_html
    )

    assert page_html.count(
        'aria-label="Empty bingo tile '
    ) == 24


def test_board_renders_tiles_by_coordinate_not_tile_id(client):
    first_tile_id = database.add_tile_with_conditions(
        "Later Board Position",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    second_tile_id = database.add_tile_with_conditions(
        "Earlier Board Position",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    assert first_tile_id < second_tile_id

    database.set_tile_board_coordinate(
        first_tile_id,
        "E5"
    )
    database.set_tile_board_coordinate(
        second_tile_id,
        "A1"
    )

    database.add_team(
        "Coordinate Order Team",
        0,
        None
    )

    login_admin(client)
    response = client.get(
        "/board/Coordinate Order Team"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    earlier_position = page_html.index(
        'data-tile="Earlier Board Position"'
    )
    later_position = page_html.index(
        'data-tile="Later Board Position"'
    )

    assert earlier_position < later_position


def test_board_renders_completed_partial_and_zero_progress_states(client):
    completed_tile_id = database.add_tile_with_conditions(
        "Completed Board Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    partial_tile_id = database.add_tile_with_conditions(
        "Partial Board Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 4
            }
        ]
    )

    zero_tile_id = database.add_tile_with_conditions(
        "Zero Board Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    database.set_tile_board_coordinate(
        completed_tile_id,
        "A1"
    )
    database.set_tile_board_coordinate(
        partial_tile_id,
        "A2"
    )
    database.set_tile_board_coordinate(
        zero_tile_id,
        "A3"
    )

    database.add_team(
        "Board Status Team",
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Board Status Team"
        )
    )

    database.add_completed_tile(
        completed_tile_id,
        team.team_id
    )

    database.add_player(
        "Board Status Player",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            "Board Status Player"
        )
    )

    database.add_player_partial_completions(
        player.player_id,
        team.team_id,
        partial_tile_id,
        0.25
    )

    login_admin(client)
    response = client.get(
        "/board/Board Status Team"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    def get_tile_button_html(tile_name):
        marker = f'data-tile="{tile_name}"'
        marker_position = page_html.index(marker)

        button_start = page_html.rfind(
            "<button",
            0,
            marker_position
        )
        button_end = page_html.index(
            "</button>",
            marker_position
        )

        return page_html[
            button_start:button_end
        ]

    completed_button = get_tile_button_html(
        "Completed Board Tile"
    )
    partial_button = get_tile_button_html(
        "Partial Board Tile"
    )
    zero_button = get_tile_button_html(
        "Zero Board Tile"
    )

    assert "#5d9a50" in completed_button
    assert "#e1c84f" in partial_button
    assert "#71808d" in zero_button

    assert (
        'data-completions="Completed: Yes"'
        in completed_button
    )
    assert (
        'data-completions="Completed: No"'
        in partial_button
    )
    assert (
        'data-completions="Completed: No"'
        in zero_button
    )


def test_get_progress_endpoint_returns_completed_status(client):
    tile_id = database.add_tile_with_conditions(
        "Completed Modal Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    database.add_team(
        "Completed Modal Team",
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Completed Modal Team"
        )
    )

    database.add_completed_tile(
        tile_id,
        team.team_id
    )

    login_admin(client)
    response = client.get(
        "/board/get_progress",
        query_string={
            "tileName": "Completed Modal Tile",
            "teamName": "Completed Modal Team"
        }
    )

    assert response.status_code == 200
    assert response.get_json() == "This tile is complete."


def test_get_progress_endpoint_returns_partial_status(client):
    tile_id = database.add_tile_with_conditions(
        "Partial Modal Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 4
            }
        ]
    )

    database.add_team(
        "Partial Modal Team",
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Partial Modal Team"
        )
    )

    database.add_player(
        "Partial Modal Player",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            "Partial Modal Player"
        )
    )

    database.add_player_partial_completions(
        player.player_id,
        team.team_id,
        tile_id,
        0.25
    )

    login_admin(client)
    response = client.get(
        "/board/get_progress",
        query_string={
            "tileName": "Partial Modal Tile",
            "teamName": "Partial Modal Team"
        }
    )

    assert response.status_code == 200
    assert response.get_json() == "Team progress: 25.00%"


def test_get_progress_endpoint_returns_killcount_partial_status(client):
    tile_id = database.add_tile_with_conditions(
        "Killcount Modal Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "KILLCOUNT",
                "condition_trigger": "vorkath",
                "target": 5000
            }
        ]
    )

    database.add_team(
        "Killcount Modal Team",
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Killcount Modal Team"
        )
    )

    database.add_player(
        "Killcount Modal Player",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            "Killcount Modal Player"
        )
    )

    database.add_player_partial_completions(
        player.player_id,
        team.team_id,
        tile_id,
        0.25
    )

    login_admin(client)
    response = client.get(
        "/board/get_progress",
        query_string={
            "tileName": "Killcount Modal Tile",
            "teamName": "Killcount Modal Team"
        }
    )

    assert response.status_code == 200
    assert (
        response.get_json()
        == "Team progress: 1,250 / 5,000 KC (25.00%)"
    )


def test_get_progress_endpoint_returns_experience_partial_status(client):
    tile_id = database.add_tile_with_conditions(
        "Experience Modal Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "EXPERIENCE",
                "condition_trigger": "woodcutting",
                "target": 2000000
            }
        ]
    )

    database.add_team(
        "Experience Modal Team",
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Experience Modal Team"
        )
    )

    database.add_player(
        "Experience Modal Player",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name(
            "Experience Modal Player"
        )
    )

    database.add_player_partial_completions(
        player.player_id,
        team.team_id,
        tile_id,
        0.25
    )

    login_admin(client)
    response = client.get(
        "/board/get_progress",
        query_string={
            "tileName": "Experience Modal Tile",
            "teamName": "Experience Modal Team"
        }
    )

    assert response.status_code == 200
    assert (
        response.get_json()
        == "Team progress: 500,000 / 2,000,000 XP (25.00%)"
    )


def test_get_progress_endpoint_returns_zero_progress_status(client):
    database.add_tile_with_conditions(
        "Zero Modal Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    database.add_team(
        "Zero Modal Team",
        0,
        None
    )

    login_admin(client)
    response = client.get(
        "/board/get_progress",
        query_string={
            "tileName": "Zero Modal Tile",
            "teamName": "Zero Modal Team"
        }
    )

    assert response.status_code == 200
    assert response.get_json() == "Team progress: 0.00%"


def test_legacy_tile_creation_rejects_twenty_sixth_tile():
    for tile_number in range(1, 26):
        create_test_tile(
            f"Legacy Capacity Tile {tile_number}"
        )

    with pytest.raises(ValueError) as error:
        create_test_tile(
            "Legacy Capacity Tile 26"
        )

    assert str(error.value) == (
        "A bingo board can contain a maximum of 25 tiles. "
        "Unassigned tiles also count towards this limit."
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                COUNT(*),
                COUNT(board_coordinate)
            FROM tiles
            '''
        )

        tile_count, assigned_count = cursor.fetchone()

    assert tile_count == 25
    assert assigned_count == 0


def test_modern_tile_creation_rejects_twenty_sixth_tile():
    conditions = [
        {
            "completion_path": 1,
            "condition_type": "MANUAL",
            "condition_trigger": None,
            "target": 1
        }
    ]

    for tile_number in range(1, 26):
        database.add_tile_with_conditions(
            f"Modern Capacity Tile {tile_number}",
            1,
            "Board regression test tile",
            conditions
        )

    with pytest.raises(ValueError) as error:
        database.add_tile_with_conditions(
            "Modern Capacity Tile 26",
            1,
            "Board regression test tile",
            conditions
        )

    assert str(error.value) == (
        "A bingo board can contain a maximum of 25 tiles. "
        "Unassigned tiles also count towards this limit."
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                COUNT(*),
                COUNT(board_coordinate)
            FROM tiles
            '''
        )

        tile_count, assigned_count = cursor.fetchone()

    assert tile_count == 25
    assert assigned_count == 0


def test_create_tile_route_rejects_twenty_sixth_tile(client):
    for tile_number in range(1, 26):
        create_test_tile(
            f"Route Capacity Existing Tile {tile_number}"
        )

    login_admin(client)

    response = client.post(
        "/tile/tiles/new",
        data={
            "tile_name": "Route Capacity Tile 26",
            "tile_points": "1",
            "tile_rules": "Board regression test tile",
            "completion_path": "1",
            "condition_type": "MANUAL",
            "condition_trigger": "",
            "condition_target": "1",
            "route_completion_path": "1",
            "route_mode": "ALL",
            "route_target": ""
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert (
        "A bingo board can contain a maximum of 25 tiles. "
        "Unassigned tiles also count towards this limit."
        in page_html
    )

    with database.connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM tiles"
        )
        tile_count = cursor.fetchone()[0]

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM tiles
            WHERE tile_name = %s
            ''',
            ("Route Capacity Tile 26",)
        )
        rejected_tile_count = cursor.fetchone()[0]

    assert tile_count == 25
    assert rejected_tile_count == 0


def test_board_without_teams_uses_completed_no_status(client):
    tile_id = database.add_tile_with_conditions(
        "No Team Board Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    database.set_tile_board_coordinate(
        tile_id,
        "A1"
    )

    login_admin(client)
    response = client.get(
        "/board/"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert (
        'data-completions="Completed: No"'
        in page_html
    )
    assert "Completions: 0" not in page_html


def test_board_requires_login(client):
    database.add_team(
        "ProtectedTeam",
        0,
        None
    )

    response = client.get(
        "/board/ProtectedTeam"
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_player_can_view_own_board_without_team_selector(client):
    _, player = create_board_team_and_player(
        "OwnBoardTeam",
        "OwnBoardPlayer"
    )

    database.add_team(
        "OtherBoardTeam",
        0,
        None
    )

    create_board_user(
        "Own Board Login",
        player_id=player.player_id
    )

    login_board_user(
        client,
        "Own Board Login"
    )

    response = client.get(
        "/board/OwnBoardTeam"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert "OwnBoardTeam" in page_html
    assert "Select Team" not in page_html
    assert "OtherBoardTeam" not in page_html
    assert "const teamnames" not in page_html


def test_player_board_index_defaults_to_own_team(client):
    _, player = create_board_team_and_player(
        "PlayerDefaultTeam",
        "PlayerDefaultBoardPlayer"
    )

    database.add_team(
        "PlayerDefaultOtherTeam",
        0,
        None
    )

    create_board_user(
        "Player Default Board Login",
        player_id=player.player_id
    )

    login_board_user(
        client,
        "Player Default Board Login"
    )

    response = client.get(
        "/board/"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/board/PlayerDefaultTeam"
    )


def test_player_other_team_board_redirects_to_own_board(client):
    _, player = create_board_team_and_player(
        "PlayerOwnTeam",
        "PlayerOwnBoardPlayer"
    )

    database.add_team(
        "PlayerOtherTeam",
        0,
        None
    )

    create_board_user(
        "Restricted Board Login",
        player_id=player.player_id
    )

    login_board_user(
        client,
        "Restricted Board Login"
    )

    response = client.get(
        "/board/PlayerOtherTeam"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/board/PlayerOwnTeam"
    )


def test_player_cannot_query_other_team_progress(client):
    database.add_tile_with_conditions(
        "Protected Progress Tile",
        1,
        "Board regression test tile",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    _, player = create_board_team_and_player(
        "ProgressOwnTeam",
        "ProgressOwnPlayer"
    )

    database.add_team(
        "ProgressOtherTeam",
        0,
        None
    )

    create_board_user(
        "Progress Restricted Login",
        player_id=player.player_id
    )

    login_board_user(
        client,
        "Progress Restricted Login"
    )

    denied_response = client.get(
        "/board/get_progress",
        query_string={
            "tileName": "Protected Progress Tile",
            "teamName": "ProgressOtherTeam"
        }
    )

    assert denied_response.status_code == 403
    assert denied_response.get_json() == (
        "You can only view progress for your own team."
    )

    own_response = client.get(
        "/board/get_progress",
        query_string={
            "tileName": "Protected Progress Tile",
            "teamName": "ProgressOwnTeam"
        }
    )

    assert own_response.status_code == 200
    assert own_response.get_json() == (
        "Team progress: 0.00%"
    )


@pytest.mark.parametrize(
    "account_role",
    [
        "ADMIN",
        "ORGANISER"
    ]
)
def test_staff_can_view_any_board_and_team_selector(
    client,
    account_role
):
    database.add_team(
        "StaffTeamOne",
        0,
        None
    )

    database.add_team(
        "StaffTeamTwo",
        0,
        None
    )

    username = (
        f"{account_role} Board Viewer"
    )

    create_board_user(
        username,
        account_role=account_role
    )

    login_board_user(
        client,
        username
    )

    response = client.get(
        "/board/StaffTeamTwo"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert "Select Team" in page_html
    assert "StaffTeamOne" in page_html
    assert "StaffTeamTwo" in page_html
    assert "const teamnames" in page_html


@pytest.mark.parametrize(
    "account_role",
    [
        "ADMIN",
        "ORGANISER"
    ]
)
def test_linked_staff_board_index_defaults_to_own_team(
    client,
    account_role
):
    database.add_team(
        "StaffOtherTeam",
        0,
        None
    )

    _, player = create_board_team_and_player(
        "StaffOwnTeam",
        f"{account_role} Linked Player"
    )

    username = (
        f"{account_role} Linked Login"
    )

    create_board_user(
        username,
        account_role=account_role,
        player_id=player.player_id
    )

    login_board_user(
        client,
        username
    )

    response = client.get(
        "/board/"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/board/StaffOwnTeam"
    )


def test_unlinked_player_cannot_browse_team_board(client):
    database.add_team(
        "UnlinkedProtectedTeam",
        0,
        None
    )

    create_board_user(
        "Unlinked Board Player"
    )

    login_board_user(
        client,
        "Unlinked Board Player"
    )

    response = client.get(
        "/board/UnlinkedProtectedTeam"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/user/account?link_required=1"
    )


def test_board_visible_flag_no_longer_hides_board(
    client,
    monkeypatch
):
    monkeypatch.setenv(
        "BOARD_VISIBLE",
        "FALSE"
    )

    database.add_team(
        "Always Visible Team",
        0,
        None
    )

    login_admin(client)

    response = client.get(
        "/board/Always Visible Team"
    )

    assert response.status_code == 200

    page_html = response.get_data(
        as_text=True
    )

    assert "Always Visible Team" in page_html
    assert "The Tiles Haven't Been Released Yet" not in page_html


def test_get_board_render_state_includes_completed_tile():
    from utils import bingo, database, db_entities

    database.add_team(
        "Shared Board State Team",
        0,
        None
    )

    team = db_entities.Team(
        database.get_team_by_name(
            "Shared Board State Team"
        )
    )

    tile_id = database.add_tile_with_conditions(
        "Shared Board Completed Tile",
        5,
        "Shared board-state helper test",
        [
            {
                "completion_path": 1,
                "condition_type": "MANUAL",
                "condition_trigger": None,
                "target": 1
            }
        ]
    )

    database.set_tile_board_coordinate(
        tile_id,
        "B2"
    )

    database.add_completed_tile(
        tile_id,
        team.team_id
    )

    board_state = bingo.get_board_render_state(
        team.team_id
    )

    assert board_state["tile_names_by_coordinate"] == {
        "B2": "Shared Board Completed Tile"
    }

    assert board_state["completed_coordinates"] == {
        "B2"
    }

    assert board_state["partial_coordinates"] == set()
