import json

import requests

from urllib.parse import urlparse


DISCORD_WEBHOOK_HOSTS = {
    "discord.com",
    "ptb.discord.com",
    "canary.discord.com"
}


def validate_discord_webhook_url(url):
    if not isinstance(url, str):
        return False

    url = url.strip()

    if not url:
        return False

    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme != "https":
        return False

    if parsed.hostname not in DISCORD_WEBHOOK_HOSTS:
        return False

    path_parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    if len(path_parts) != 4:
        return False

    if (
        path_parts[0] != "api"
        or path_parts[1] != "webhooks"
    ):
        return False

    webhook_id = path_parts[2]
    webhook_token = path_parts[3]

    if not webhook_id.isdigit():
        return False

    if not webhook_token:
        return False

    return True


def send_test_webhook(url, message):
    url = str(url or "").strip()

    if not validate_discord_webhook_url(url):
        raise ValueError(
            "Please enter a valid Discord webhook URL."
        )

    try:
        response = requests.post(
            url,
            json={
                "content": message
            },
            timeout=10
        )
    except requests.RequestException as error:
        raise RuntimeError(
            "Discord could not be reached to test this webhook."
        ) from error

    if not response.ok:
        raise RuntimeError(
            "Discord rejected the test webhook. "
            "Please check the webhook URL and try again."
        )

    return True


def send_webhook(url, title, description, color, image):
    """
    Send a webhook to the specified URL with an embed and an image file.

    :param url: The URL to which the webhook should be sent.
    :param title: The title of the embed.
    :param description: The description of the embed.
    :param color: The color of the embed.
    :param image_file: (Optional) The FileStorage object containing the image to be sent.
    """
    # Assuming 'image_file' is a SpooledTemporaryFile object from Flask's request.files

    embeds = [
        {
            'title': title,
            'color': color,
            'description': description,
            'image': {
                'url': 'attachment://lootImage.png'
            }
        }
    ]

    if image is not None:
        image.save('lootImage.png')
        with open("lootImage.png", "rb") as imageData:
            files = {
                'file': ('lootImage.png', imageData, 'image/png')
            }

            payload = {
                'embeds': embeds
            }

            requests.post(url, data = {'payload_json': json.dumps(payload)}, files=files)
    else:
        payload = {
            'embeds': embeds
        }

        requests.post(url, data = {'payload_json': json.dumps(payload)})


def send_completion_webhook(
    url,
    message,
    board_image,
    discord_role_id=None
):
    url = str(url or "").strip()

    if not validate_discord_webhook_url(url):
        raise ValueError(
            "Please enter a valid Discord webhook URL."
        )

    message = str(message or "").strip()

    payload = {
        "content": message,
        "allowed_mentions": {
            "parse": []
        }
    }

    if discord_role_id is not None:
        role_id = str(discord_role_id)

        payload["content"] = (
            f"<@&{role_id}>\n"
            f"{message}"
        )

        payload["allowed_mentions"]["roles"] = [
            role_id
        ]

    try:
        response = requests.post(
            url,
            data={
                "payload_json": json.dumps(payload)
            },
            files={
                "file": (
                    "bingo_board.png",
                    board_image,
                    "image/png"
                )
            },
            timeout=10
        )
    except requests.RequestException as error:
        raise RuntimeError(
            "Discord could not be reached to send the "
            "bingo completion notification."
        ) from error

    if not response.ok:
        raise RuntimeError(
            "Discord rejected the bingo completion "
            "notification."
        )

    return True
