from dataclasses import dataclass
from math import ceil

from utils.team_balancing import BOSS_SCORE_FIELDS


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
