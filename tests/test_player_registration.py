import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cogs.UserCog as user_cog_module
from cogs.UserCog import UserCog
from utils import database


@pytest.fixture(autouse=True)
def player_registration_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Player registration tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


class FakeRegisterContext:
    def __init__(
        self,
        author_id=12345,
        display_name="Clan Nickname",
        username="discord.username",
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


def run_register(ctx, rsn):
    cog = UserCog(
        bot=None
    )

    return asyncio.run(
        UserCog.register.callback(
            cog,
            ctx,
            rsn
        )
    )


def create_player(player_name):
    database.add_team(
        "Registration Team",
        0,
        ""
    )

    team = database.get_team_by_name(
        "Registration Team"
    )

    database.add_player(
        player_name,
        0,
        0,
        0,
        team[3],
        0
    )

    return database.get_player_by_name(
        player_name
    )


def test_link_player_to_discord_stores_identity():
    player = create_player(
        "Link Tester"
    )

    database.link_player_to_discord(
        player[0],
        111111111111111111,
        "First Nickname",
        "first.username"
    )

    linked_player = database.get_player_by_name(
        "Link Tester"
    )

    assert linked_player[7] == 111111111111111111
    assert linked_player[10] == "First Nickname"
    assert linked_player[11] == "first.username"


def test_link_player_to_discord_allows_same_id_refresh():
    player = create_player(
        "Refresh Tester"
    )

    database.link_player_to_discord(
        player[0],
        222222222222222222,
        "Old Nickname",
        "old.username"
    )

    database.link_player_to_discord(
        player[0],
        222222222222222222,
        "New Nickname",
        "new.username"
    )

    linked_player = database.get_player_by_name(
        "Refresh Tester"
    )

    assert linked_player[7] == 222222222222222222
    assert linked_player[10] == "New Nickname"
    assert linked_player[11] == "new.username"


def test_link_player_to_discord_rejects_different_id():
    player = create_player(
        "Ownership Tester"
    )

    database.link_player_to_discord(
        player[0],
        333333333333333333,
        "Owner Nickname",
        "owner.username"
    )

    database.link_player_to_discord(
        player[0],
        444444444444444444,
        "Attacker Nickname",
        "attacker.username"
    )

    linked_player = database.get_player_by_name(
        "Ownership Tester"
    )

    assert linked_player[7] == 333333333333333333
    assert linked_player[10] == "Owner Nickname"
    assert linked_player[11] == "owner.username"


def test_register_refreshes_only_existing_discord_link(
    monkeypatch
):
    existing_player = (
        5,
        "Existing RSN",
        0,
        0,
        0,
        2,
        0,
        555555555555555555,
        0,
        None,
        "Old Nickname",
        "old.username"
    )

    link_calls = []

    monkeypatch.setattr(
        database,
        "get_player_by_discord_user_id",
        lambda discord_user_id: (
            existing_player
            if discord_user_id == 555555555555555555
            else None
        )
    )

    monkeypatch.setattr(
        database,
        "link_player_to_discord",
        lambda *args: link_calls.append(args)
    )

    monkeypatch.setattr(
        user_cog_module,
        "get_group_member",
        lambda rsn: pytest.fail(
            "An already-linked Discord account should not "
            "look up the supplied RSN."
        )
    )

    ctx = FakeRegisterContext(
        author_id=555555555555555555,
        display_name="Updated Nickname",
        username="updated.username"
    )

    run_register(
        ctx,
        "Someone Else"
    )

    assert link_calls == [
        (
            5,
            555555555555555555,
            "Updated Nickname",
            "updated.username"
        )
    ]

    assert len(ctx.responses) == 1
    assert (
        "already linked to **Existing RSN**"
        in ctx.responses[0]["content"]
    )


def test_register_new_link_stores_discord_names(
    monkeypatch
):
    player_tuple = (
        7,
        "New RSN",
        0,
        0,
        0,
        3,
        0,
        None,
        0,
        9001,
        None,
        None
    )

    team_tuple = (
        "New Team",
        0,
        "",
        3,
        777
    )

    link_calls = []

    monkeypatch.setattr(
        database,
        "get_player_by_discord_user_id",
        lambda discord_user_id: None
    )

    monkeypatch.setattr(
        database,
        "get_team_by_discord_role_id",
        lambda role_id: (
            team_tuple
            if role_id == 777
            else None
        )
    )

    monkeypatch.setattr(
        user_cog_module,
        "get_group_member",
        lambda rsn: {
            "displayName": "New RSN"
        }
    )

    monkeypatch.setattr(
        database,
        "get_player_by_name",
        lambda player_name: player_tuple
    )

    monkeypatch.setattr(
        database,
        "link_player_to_discord",
        lambda *args: link_calls.append(args)
    )

    ctx = FakeRegisterContext(
        author_id=666666666666666666,
        display_name="New Clan Nickname",
        username="new.username",
        roles=[
            SimpleNamespace(
                id=777
            )
        ]
    )

    run_register(
        ctx,
        "New RSN"
    )

    assert link_calls == [
        (
            7,
            666666666666666666,
            "New Clan Nickname",
            "new.username"
        )
    ]

    assert len(ctx.responses) == 1
    assert "Registration complete" in ctx.responses[0]["content"]