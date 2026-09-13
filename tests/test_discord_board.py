import asyncio
import os
from types import SimpleNamespace

import pytest

from cogs.UserCog import UserCog
from utils import database


@pytest.fixture(autouse=True)
def discord_board_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Discord board tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


class FakeBoardContext:
    def __init__(
        self,
        *,
        author_id=12345,
        display_name="Board Tester",
        username="board.tester",
        roles=None
    ):
        self.author = SimpleNamespace(
            id=author_id,
            display_name=display_name,
            name=username,
            roles=roles or []
        )

        self.deferred = False
        self.responses = []

    async def defer(self, ephemeral=False):
        self.deferred = True
        self.defer_ephemeral = ephemeral

    async def respond(
        self,
        content=None,
        **kwargs
    ):
        self.responses.append(
            {
                "content": content,
                **kwargs
            }
        )


def run_board(
    ctx,
    *,
    clean_board=False,
    team_name=None
):
    cog = UserCog(
        bot=None
    )

    return asyncio.run(
        UserCog.board.callback(
            cog,
            ctx,
            clean_board,
            team_name
        )
    )


def create_board_team_and_player(
    team_name,
    player_name,
    *,
    discord_user_id=None
):
    database.add_team(
        team_name,
        0,
        ""
    )

    team = database.get_team_by_name(
        team_name
    )

    database.add_player(
        player_name,
        0,
        0,
        0,
        team[3],
        0
    )

    player = database.get_player_by_name(
        player_name
    )

    if discord_user_id is not None:
        database.link_player_to_discord(
            player[0],
            discord_user_id,
            player_name,
            f"{player_name.lower().replace(' ', '.')}.discord"
        )

        player = database.get_player_by_name(
            player_name
        )

    return team, player


def test_linked_player_defaults_to_own_team_board():
    author_id = 111111111111111111

    create_board_team_and_player(
        "Linked Player Team",
        "Linked Board Player",
        discord_user_id=author_id
    )

    ctx = FakeBoardContext(
        author_id=author_id
    )

    run_board(
        ctx
    )

    assert ctx.deferred is True
    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "**Linked Player Team Bingo Board**"
    )
    assert (
        ctx.responses[0]["file"].filename
        == "bingo_board.png"
    )


def test_linked_player_can_request_clean_board():
    author_id = 222222222222222222

    create_board_team_and_player(
        "Clean Request Team",
        "Clean Request Player",
        discord_user_id=author_id
    )

    ctx = FakeBoardContext(
        author_id=author_id
    )

    run_board(
        ctx,
        clean_board=True
    )

    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "**Clean Bingo Board**"
    )
    assert (
        ctx.responses[0]["file"].filename
        == "bingo_board.png"
    )


def test_unlinked_standard_user_defaults_to_clean_board():
    ctx = FakeBoardContext(
        author_id=333333333333333333
    )

    run_board(
        ctx
    )

    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "**Clean Bingo Board**"
    )
    assert (
        ctx.responses[0]["file"].filename
        == "bingo_board.png"
    )


def test_standard_user_cannot_select_another_team():
    database.add_team(
        "Restricted Target Team",
        0,
        ""
    )

    ctx = FakeBoardContext(
        author_id=444444444444444444
    )

    run_board(
        ctx,
        team_name="Restricted Target Team"
    )

    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "Only Bingo Organisers can inspect another "
        "team's board."
    )


def test_linked_organiser_defaults_to_own_team_board(
    monkeypatch
):
    organiser_role_id = 999999999999999999
    author_id = 555555555555555555

    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        str(organiser_role_id)
    )

    create_board_team_and_player(
        "Organiser Own Team",
        "Linked Organiser",
        discord_user_id=author_id
    )

    ctx = FakeBoardContext(
        author_id=author_id,
        roles=[
            SimpleNamespace(
                id=organiser_role_id
            )
        ]
    )

    run_board(
        ctx
    )

    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "**Organiser Own Team Bingo Board**"
    )
    assert (
        ctx.responses[0]["file"].filename
        == "bingo_board.png"
    )


def test_unlinked_organiser_defaults_to_clean_board(
    monkeypatch
):
    organiser_role_id = 999999999999999999

    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        str(organiser_role_id)
    )

    ctx = FakeBoardContext(
        author_id=666666666666666666,
        roles=[
            SimpleNamespace(
                id=organiser_role_id
            )
        ]
    )

    run_board(
        ctx
    )

    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "**Clean Bingo Board**"
    )
    assert (
        ctx.responses[0]["file"].filename
        == "bingo_board.png"
    )


def test_organiser_can_select_another_team(
    monkeypatch
):
    organiser_role_id = 999999999999999999
    author_id = 777777777777777777

    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        str(organiser_role_id)
    )

    create_board_team_and_player(
        "Organiser Home Team",
        "Organiser Viewer",
        discord_user_id=author_id
    )

    database.add_team(
        "Organiser Target Team",
        0,
        ""
    )

    ctx = FakeBoardContext(
        author_id=author_id,
        roles=[
            SimpleNamespace(
                id=organiser_role_id
            )
        ]
    )

    run_board(
        ctx,
        team_name="Organiser Target Team"
    )

    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "**Organiser Target Team Bingo Board**"
    )
    assert (
        ctx.responses[0]["file"].filename
        == "bingo_board.png"
    )


def test_board_rejects_clean_and_team_options_together(
    monkeypatch
):
    organiser_role_id = 999999999999999999

    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        str(organiser_role_id)
    )

    database.add_team(
        "Conflicting Option Team",
        0,
        ""
    )

    ctx = FakeBoardContext(
        author_id=888888888888888888,
        roles=[
            SimpleNamespace(
                id=organiser_role_id
            )
        ]
    )

    run_board(
        ctx,
        clean_board=True,
        team_name="Conflicting Option Team"
    )

    assert len(ctx.responses) == 1
    assert ctx.responses[0]["content"] == (
        "Choose either a clean board or a team board, "
        "not both."
    )
    assert "file" not in ctx.responses[0]


def test_board_passes_progress_coordinates_to_renderer(
    monkeypatch
):
    from io import BytesIO

    author_id = 999999999999999991

    team, player = create_board_team_and_player(
        "Renderer Wiring Team",
        "Renderer Wiring Player",
        discord_user_id=author_id
    )

    completed_tile_id = database.add_tile_with_conditions(
        "Renderer Completed Tile",
        1,
        "Discord board renderer wiring test",
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
        "Renderer Partial Tile",
        1,
        "Discord board renderer wiring test",
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
        "Renderer Zero Tile",
        1,
        "Discord board renderer wiring test",
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

    database.add_completed_tile(
        completed_tile_id,
        team[3]
    )

    database.add_player_partial_completions(
        player[0],
        team[3],
        partial_tile_id,
        0.25
    )

    captured_renderer_args = {}

    def fake_render_bingo_board(
        tile_names_by_coordinate,
        *,
        completed_coordinates=None,
        partial_coordinates=None,
        show_progress=True
    ):
        captured_renderer_args["tile_names"] = (
            tile_names_by_coordinate
        )
        captured_renderer_args["completed"] = set(
            completed_coordinates or []
        )
        captured_renderer_args["partial"] = set(
            partial_coordinates or []
        )
        captured_renderer_args["show_progress"] = (
            show_progress
        )

        return BytesIO(b"fake png")

    monkeypatch.setattr(
        "cogs.UserCog.board_renderer.render_bingo_board",
        fake_render_bingo_board
    )

    ctx = FakeBoardContext(
        author_id=author_id
    )

    run_board(
        ctx
    )

    assert captured_renderer_args["tile_names"] == {
        "A1": "Renderer Completed Tile",
        "A2": "Renderer Partial Tile",
        "A3": "Renderer Zero Tile"
    }

    assert captured_renderer_args["completed"] == {
        "A1"
    }

    assert captured_renderer_args["partial"] == {
        "A2"
    }

    assert captured_renderer_args["show_progress"] is True