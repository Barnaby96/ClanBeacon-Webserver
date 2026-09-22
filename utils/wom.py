import os

import requests

from utils.branding import get_wom_user_agent


class WiseOldManError(Exception):
    """Raised when Wise Old Man data cannot be retrieved."""


def _get_headers():
    headers = {
        "User-Agent": get_wom_user_agent()
    }

    api_key = os.getenv("WOM_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    return headers


def get_group(group_id):
    try:
        group_id = int(group_id)
    except (
        TypeError,
        ValueError
    ) as error:
        raise WiseOldManError(
            "The Wise Old Man group ID must be a number."
        ) from error

    try:
        response = requests.get(
            f"https://api.wiseoldman.net/v2/groups/{group_id}",
            headers=_get_headers(),
            timeout=20
        )

        if response.status_code == 404:
            raise WiseOldManError(
                f"Wise Old Man group {group_id} was not found."
            )

        response.raise_for_status()
        data = response.json()

    except WiseOldManError:
        raise
    except (
        requests.RequestException,
        ValueError
    ) as error:
        raise WiseOldManError(
            "Unable to retrieve the Wise Old Man group."
        ) from error

    return data


def get_player(rsn):
    rsn = str(
        rsn or ""
    ).strip()

    if not rsn:
        raise WiseOldManError(
            "A player name is required for Wise Old Man lookup."
        )

    try:
        response = requests.get(
            f"https://api.wiseoldman.net/v2/players/{rsn}",
            headers=_get_headers(),
            timeout=20
        )

        if response.status_code == 404:
            raise WiseOldManError(
                f"Wise Old Man player '{rsn}' was not found."
            )

        response.raise_for_status()
        data = response.json()

    except WiseOldManError:
        raise
    except (
        requests.RequestException,
        ValueError
    ) as error:
        raise WiseOldManError(
            f"Unable to retrieve Wise Old Man player '{rsn}'."
        ) from error

    return data


def get_group_member(rsn):
    group_id = os.getenv("WOM_GROUP_ID")
    if not group_id:
        raise WiseOldManError("WOM_GROUP_ID is not configured.")

    data = get_group(
        group_id
    )

    requested_rsn = rsn.strip().lower()

    for membership in data.get("memberships", []):
        player = membership.get("player") or {}

        username = str(player.get("username", "")).strip()
        display_name = str(player.get("displayName", "")).strip()

        if requested_rsn in {
            username.lower(),
            display_name.lower()
        }:
            return player

    return None


def get_competition_details(competition_id, metric=None):
    try:
        competition_id = int(competition_id)
    except (TypeError, ValueError) as error:
        raise WiseOldManError(
            "The Wise Old Man competition ID must be a number."
        ) from error

    params = {}
    if metric:
        params["metric"] = metric

    try:
        response = requests.get(
            f"https://api.wiseoldman.net/v2/competitions/{competition_id}",
            headers=_get_headers(),
            params=params,
            timeout=20
        )

        if response.status_code == 404:
            raise WiseOldManError(
                f"Wise Old Man competition {competition_id} was not found."
            )

        response.raise_for_status()
        data = response.json()

    except WiseOldManError:
        raise
    except (requests.RequestException, ValueError) as error:
        raise WiseOldManError(
            "Unable to retrieve the Wise Old Man competition."
        ) from error

    return data


def update_player(rsn):
    rsn = str(rsn or "").strip()

    if not rsn:
        raise WiseOldManError(
            "A player name is required for Wise Old Man update."
        )

    try:
        response = requests.post(
            f"https://api.wiseoldman.net/v2/players/{rsn}",
            headers=_get_headers(),
            timeout=30
        )

        if response.status_code == 404:
            raise WiseOldManError(
                f"Wise Old Man player '{rsn}' was not found."
            )

        if response.status_code == 429:
            raise WiseOldManError(
                f"Wise Old Man rejected '{rsn}' because they were updated "
                "too recently. Try again in a minute or two."
            )

        response.raise_for_status()
        data = response.json()

    except WiseOldManError:
        raise
    except (requests.RequestException, ValueError) as error:
        raise WiseOldManError(
            f"Unable to update Wise Old Man player '{rsn}'."
        ) from error

    return data


def update_players(rsns):
    results = {
        "updated": [],
        "failed": []
    }

    seen_players = set()

    for rsn in rsns:
        player_name = str(rsn or "").strip()

        if not player_name:
            continue

        player_key = player_name.casefold()

        if player_key in seen_players:
            continue

        seen_players.add(
            player_key
        )

        try:
            update_player(
                player_name
            )
        except WiseOldManError as error:
            results["failed"].append(
                {
                    "player_name": player_name,
                    "error": str(error)
                }
            )
        else:
            results["updated"].append(
                player_name
            )

    return results
