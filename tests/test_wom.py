import pytest
import requests

from utils import wom


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        payload=None
    ):
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}"
            )

    def json(self):
        return self.payload


def test_get_group_fetches_wise_old_man_group(monkeypatch):
    calls = []

    def fake_get(
        url,
        headers,
        timeout
    ):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout
            }
        )

        return FakeResponse(
            payload={
                "id": 25798,
                "name": "Indoor Sky",
                "memberships": []
            }
        )

    monkeypatch.setattr(
        wom.requests,
        "get",
        fake_get
    )

    result = wom.get_group(
        25798
    )

    assert result["id"] == 25798
    assert result["name"] == "Indoor Sky"
    assert calls == [
        {
            "url": "https://api.wiseoldman.net/v2/groups/25798",
            "headers": wom._get_headers(),
            "timeout": 20
        }
    ]


def test_get_group_requires_numeric_group_id():
    with pytest.raises(
        wom.WiseOldManError,
        match="group ID must be a number"
    ):
        wom.get_group(
            "not-a-number"
        )


def test_get_group_reports_missing_group(monkeypatch):
    monkeypatch.setattr(
        wom.requests,
        "get",
        lambda url, headers, timeout: FakeResponse(
            status_code=404
        )
    )

    with pytest.raises(
        wom.WiseOldManError,
        match="group 25798 was not found"
    ):
        wom.get_group(
            25798
        )


def test_get_player_fetches_wise_old_man_player(monkeypatch):
    calls = []

    def fake_get(
        url,
        headers,
        timeout
    ):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout
            }
        )

        return FakeResponse(
            payload={
                "id": 12345,
                "displayName": "Psychossass1",
                "combatLevel": 126,
                "latestSnapshot": {
                    "data": {
                        "skills": {
                            "overall": {
                                "level": 2138
                            }
                        }
                    }
                }
            }
        )

    monkeypatch.setattr(
        wom.requests,
        "get",
        fake_get
    )

    result = wom.get_player(
        "Psychossass1"
    )

    assert result["displayName"] == "Psychossass1"
    assert result["combatLevel"] == 126
    assert calls == [
        {
            "url": "https://api.wiseoldman.net/v2/players/Psychossass1",
            "headers": wom._get_headers(),
            "timeout": 20
        }
    ]


def test_get_player_requires_name():
    with pytest.raises(
        wom.WiseOldManError,
        match="A player name is required"
    ):
        wom.get_player(
            ""
        )


def test_get_player_reports_missing_player(monkeypatch):
    monkeypatch.setattr(
        wom.requests,
        "get",
        lambda url, headers, timeout: FakeResponse(
            status_code=404
        )
    )

    with pytest.raises(
        wom.WiseOldManError,
        match="player 'Missing Player' was not found"
    ):
        wom.get_player(
            "Missing Player"
        )
