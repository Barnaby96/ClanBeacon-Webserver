from dataclasses import dataclass
from math import ceil

from utils.team_balancing import (
    BOSS_SCORE_FIELDS,
    calculate_player_balance_scores,
)


CAPABILITY_SCORE_FIELDS = (
    "skilling_score",
    *BOSS_SCORE_FIELDS,
)


@dataclass(frozen=True)
class CapabilityProfile:
    profile_id: str
    display_name: str
    player_count: int
    scores: dict

    def score_for(self, score_field):
        return float(
            self.scores.get(
                score_field,
                0
            )
            or 0
        )


@dataclass(frozen=True)
class CapabilityProfileSet:
    source: str
    profiles: tuple[CapabilityProfile, ...]
    estimated_team_size: int | None = None

    @property
    def has_profiles(self):
        return bool(
            self.profiles
        )



@dataclass(frozen=True)
class CapabilityProfileBuildResult:
    profile_set: CapabilityProfileSet
    failed_players: tuple[dict, ...] = ()


def _safe_float(value):
    try:
        return float(
            value or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def build_capability_profile_from_team(team):
    players = tuple(
        team.get(
            "players",
            ()
        )
        or ()
    )

    team_name = str(
        team.get(
            "team_name",
            ""
        )
        or ""
    ).strip()

    team_id = str(
        team.get(
            "team_id",
            team_name,
        )
        or team_name
        or "team"
    )

    return CapabilityProfile(
        profile_id=team_id,
        display_name=team_name or team_id,
        player_count=len(
            players
        ),
        scores={
            score_field: _safe_float(
                team.get(
                    score_field,
                    0,
                )
            )
            for score_field in CAPABILITY_SCORE_FIELDS
        },
    )


def build_capability_profiles_from_teams(teams):
    return CapabilityProfileSet(
        source="teams",
        profiles=tuple(
            build_capability_profile_from_team(
                team
            )
            for team in teams
        ),
    )


def build_average_team_capability_profile_from_players(
    players,
    estimated_team_size,
):
    players = tuple(
        players
        or ()
    )
    estimated_team_size = int(
        estimated_team_size
    )

    if estimated_team_size < 1:
        raise ValueError(
            "Estimated team size must be at least 1."
        )

    estimated_team_count = max(
        ceil(
            len(
                players
            )
            / estimated_team_size
        ),
        1,
    )

    scores = {}

    for score_field in CAPABILITY_SCORE_FIELDS:
        scores[score_field] = (
            sum(
                _safe_float(
                    player.get(
                        score_field,
                        0,
                    )
                )
                for player in players
            )
            / estimated_team_count
        )

    return CapabilityProfileSet(
        source="wom_group_average",
        estimated_team_size=estimated_team_size,
        profiles=(
            CapabilityProfile(
                profile_id="estimated_average_team",
                display_name="Estimated average team",
                player_count=min(
                    len(
                        players
                    ),
                    estimated_team_size,
                ),
                scores=scores,
            ),
        ),
    )


def _extract_rostered_player_name(player_row):
    if isinstance(
        player_row,
        dict,
    ):
        return str(
            player_row.get("player_name")
            or player_row.get("displayName")
            or player_row.get("username")
            or ""
        ).strip()

    if isinstance(
        player_row,
        (
            tuple,
            list,
        ),
    ):
        if len(player_row) >= 2:
            return str(
                player_row[1]
            ).strip()

        if player_row:
            return str(
                player_row[0]
            ).strip()

        return ""

    return str(
        player_row or ""
    ).strip()


def build_capability_profiles_from_rostered_players(
    players_by_team,
    fetch_player,
    score_player=calculate_player_balance_scores,
):
    teams = []
    failed_players = []

    for team_name, player_rows in (
        players_by_team or {}
    ).items():
        scored_players = []

        for player_row in player_rows or ():
            player_name = _extract_rostered_player_name(
                player_row
            )

            if not player_name:
                continue

            try:
                scored_players.append(
                    score_player(
                        fetch_player(
                            player_name
                        )
                    )
                )
            except Exception as error:
                failed_players.append(
                    {
                        "team_name": str(
                            team_name
                        ),
                        "player_name": player_name,
                        "error": str(
                            error
                        ),
                    }
                )

        team = {
            "team_id": str(
                team_name
            ),
            "team_name": str(
                team_name
            ),
            "players": scored_players,
        }

        for score_field in CAPABILITY_SCORE_FIELDS:
            team[score_field] = sum(
                _safe_float(
                    player.get(
                        score_field,
                        0,
                    )
                )
                for player in scored_players
            )

        teams.append(
            team
        )

    return CapabilityProfileBuildResult(
        profile_set=CapabilityProfileSet(
            source="current_teams",
            profiles=tuple(
                build_capability_profile_from_team(
                    team
                )
                for team in teams
            ),
        ),
        failed_players=tuple(
            failed_players
        ),
    )
