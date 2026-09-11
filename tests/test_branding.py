from utils import branding


def test_bot_name_uses_committed_default(monkeypatch):
    monkeypatch.delenv(
        "BOT_NAME",
        raising=False
    )

    assert (
        branding.get_bot_name()
        == branding.DEFAULT_BOT_NAME
    )


def test_bot_name_uses_environment_override(monkeypatch):
    monkeypatch.setenv(
        "BOT_NAME",
        "Indoor Sky Bingo Bot"
    )

    assert (
        branding.get_bot_name()
        == "Indoor Sky Bingo Bot"
    )


def test_blank_bot_name_falls_back_to_default(monkeypatch):
    monkeypatch.setenv(
        "BOT_NAME",
        "   "
    )

    assert (
        branding.get_bot_name()
        == branding.DEFAULT_BOT_NAME
    )


def test_wom_user_agent_defaults_to_bot_name(monkeypatch):
    monkeypatch.delenv(
        "WOM_USER_AGENT",
        raising=False
    )

    monkeypatch.setattr(
        branding,
        "BOT_NAME",
        "Indoor Sky Bingo Bot"
    )

    assert (
        branding.get_wom_user_agent()
        == "Indoor Sky Bingo Bot Development"
    )


def test_explicit_wom_user_agent_takes_precedence(
    monkeypatch
):
    monkeypatch.setenv(
        "WOM_USER_AGENT",
        "Custom WOM Identifier"
    )

    monkeypatch.setattr(
        branding,
        "BOT_NAME",
        "Indoor Sky Bingo Bot"
    )

    assert (
        branding.get_wom_user_agent()
        == "Custom WOM Identifier"
    )