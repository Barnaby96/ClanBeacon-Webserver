from types import SimpleNamespace

import pytest
import requests

from utils import send_webhook


VALID_WEBHOOK_URL = (
    "https://discord.com/api/webhooks/"
    "123456789012345678/"
    "test-webhook-token"
)


@pytest.mark.parametrize(
    "url",
    [
        VALID_WEBHOOK_URL,
        (
            "https://ptb.discord.com/api/webhooks/"
            "123456789012345678/test-token"
        ),
        (
            "https://canary.discord.com/api/webhooks/"
            "123456789012345678/test-token"
        )
    ]
)
def test_validate_discord_webhook_url_accepts_supported_urls(
    url
):
    assert (
        send_webhook.validate_discord_webhook_url(url)
        is True
    )


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not-a-url",
        (
            "http://discord.com/api/webhooks/"
            "123456789012345678/test-token"
        ),
        (
            "https://discord.com.example.com/api/webhooks/"
            "123456789012345678/test-token"
        ),
        (
            "https://example.com/api/webhooks/"
            "123456789012345678/test-token"
        ),
        (
            "https://discord.com/api/webhooks/"
            "not-a-number/test-token"
        ),
        (
            "https://discord.com/api/webhooks/"
            "123456789012345678"
        ),
        (
            "https://discord.com/channels/"
            "123456789012345678/test-token"
        )
    ]
)
def test_validate_discord_webhook_url_rejects_unsafe_urls(
    url
):
    assert (
        send_webhook.validate_discord_webhook_url(url)
        is False
    )


def test_send_test_webhook_posts_expected_message(
    monkeypatch
):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout

        return SimpleNamespace(
            ok=True
        )

    monkeypatch.setattr(
        send_webhook.requests,
        "post",
        fake_post
    )

    result = send_webhook.send_test_webhook(
        VALID_WEBHOOK_URL,
        "This is a test message for team Zamorak."
    )

    assert result is True
    assert captured == {
        "url": VALID_WEBHOOK_URL,
        "json": {
            "content": (
                "This is a test message for team Zamorak."
            )
        },
        "timeout": 10
    }


def test_send_test_webhook_rejects_invalid_url_without_request(
    monkeypatch
):
    def unexpected_post(*args, **kwargs):
        pytest.fail(
            "Invalid webhook URL must not make a request."
        )

    monkeypatch.setattr(
        send_webhook.requests,
        "post",
        unexpected_post
    )

    with pytest.raises(
        ValueError,
        match="valid Discord webhook URL"
    ):
        send_webhook.send_test_webhook(
            "https://example.com/api/webhooks/123/token",
            "Test"
        )


def test_send_test_webhook_reports_discord_rejection(
    monkeypatch
):
    monkeypatch.setattr(
        send_webhook.requests,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            ok=False
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Discord rejected the test webhook"
    ):
        send_webhook.send_test_webhook(
            VALID_WEBHOOK_URL,
            "Test"
        )


def test_send_test_webhook_reports_connection_failure(
    monkeypatch
):
    def failed_post(*args, **kwargs):
        raise requests.RequestException(
            "Test connection failure"
        )

    monkeypatch.setattr(
        send_webhook.requests,
        "post",
        failed_post
    )

    with pytest.raises(
        RuntimeError,
        match="Discord could not be reached"
    ):
        send_webhook.send_test_webhook(
            VALID_WEBHOOK_URL,
            "Test"
        )


def test_send_completion_webhook_posts_board_and_role_mention(
    monkeypatch
):
    captured = {}

    class FakeResponse:
        ok = True

    def fake_post(
        url,
        data,
        files,
        timeout
    ):
        captured["url"] = url
        captured["data"] = data
        captured["files"] = files
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        send_webhook.requests,
        "post",
        fake_post
    )

    board_image = __import__("io").BytesIO(
        b"test-board-image"
    )

    result = send_webhook.send_completion_webhook(
        VALID_WEBHOOK_URL,
        (
            "Congratulations Zamorak, you have completed "
            "Obtain 30 Feathers at A1! You have gained "
            "5 Bingo Points!"
        ),
        board_image,
        discord_role_id=123456789012345678
    )

    assert result is True
    assert captured["url"] == VALID_WEBHOOK_URL
    assert captured["timeout"] == 10

    payload = send_webhook.json.loads(
        captured["data"]["payload_json"]
    )

    assert payload == {
        "content": (
            "<@&123456789012345678>\n"
            "Congratulations Zamorak, you have completed "
            "Obtain 30 Feathers at A1! You have gained "
            "5 Bingo Points!"
        ),
        "allowed_mentions": {
            "parse": [],
            "roles": [
                "123456789012345678"
            ]
        }
    }

    assert "file" in captured["files"]

    filename, file_data, content_type = (
        captured["files"]["file"]
    )

    assert filename == "bingo_board.png"
    assert content_type == "image/png"
    assert file_data.read() == b"test-board-image"
