import os


DEFAULT_BOT_NAME = "ClanBeacon"


def get_bot_name():
    return (
        os.getenv(
            "BOT_NAME",
            DEFAULT_BOT_NAME
        ).strip()
        or DEFAULT_BOT_NAME
    )


BOT_NAME = get_bot_name()


def get_wom_user_agent():
    configured_user_agent = os.getenv(
        "WOM_USER_AGENT",
        ""
    ).strip()

    if configured_user_agent:
        return configured_user_agent

    return f"{BOT_NAME} Development"