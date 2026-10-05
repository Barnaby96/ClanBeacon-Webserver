from pathlib import Path

import routes.admin.admin_routes as admin_routes


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generated_board_preview_route_renders_summary(monkeypatch):
    captured = {}

    expected_summary = object()

    class FakeCapabilityResult:
        failed_players = ()
        profile_set = "capability-profiles"

    def fake_get_summary(capability_profiles=None):
        captured["capability_profiles"] = capability_profiles
        return expected_summary

    def fake_build_capability_profiles(players_by_team, fetch_player):
        captured["players_by_team"] = players_by_team
        captured["fetch_player"] = fetch_player
        return FakeCapabilityResult()

    monkeypatch.setattr(
        admin_routes.database,
        "get_players_by_team",
        lambda: {
            "Team One": [
                (
                    1,
                    "Player One",
                ),
            ],
        }
    )
    monkeypatch.setattr(
        admin_routes.wom,
        "get_player",
        "fetch-player"
    )
    monkeypatch.setattr(
        admin_routes,
        "build_capability_profiles_from_rostered_players",
        fake_build_capability_profiles
    )
    monkeypatch.setattr(
        admin_routes,
        "get_curated_generated_board_preview_summary",
        fake_get_summary
    )

    def fake_render_template(template_name, **context):
        captured["template_name"] = template_name
        captured["context"] = context
        return "rendered"

    monkeypatch.setattr(
        admin_routes,
        "render_template",
        fake_render_template
    )

    route_function = getattr(
        admin_routes.generated_board_preview,
        "__wrapped__",
        admin_routes.generated_board_preview
    )

    assert route_function() == "rendered"
    assert captured["template_name"] == (
        "admin_templates/generated_board_preview.html"
    )
    assert captured["players_by_team"] == {
        "Team One": [
            (
                1,
                "Player One",
            ),
        ],
    }
    assert captured["fetch_player"] == "fetch-player"
    assert captured["capability_profiles"] == "capability-profiles"
    assert captured["context"]["summary"] is expected_summary


def test_bingo_setup_links_to_generated_board_preview():
    template = (
        PROJECT_ROOT / "templates/admin_templates/bingo_setup.html"
    ).read_text(
        encoding="utf-8"
    )

    assert "Preview Generated Board" in template
    assert "admin_routes.generated_board_preview" in template


def test_generated_board_preview_template_contains_expected_sections():
    template = (
        PROJECT_ROOT / "templates/admin_templates/generated_board_preview.html"
    ).read_text(
        encoding="utf-8"
    )

    assert "Generated Board Preview" in template
    assert "Back to Bingo Setup" in template
    assert "summary.rows_by_point_value|dictsort" in template
    assert "summary.counts_by_point_value|dictsort" in template
    assert "summary.counts_by_primary_category|dictsort" in template
    assert "Capability" in template
    assert "row.capability_summary_text" in template
    assert "row.capability_warning_level" in template
    assert "generated-board-preview" in template
    assert "color: #2b1a0b;" in template


def test_generated_board_preview_route_flashes_wom_failures(monkeypatch):
    captured = {
        "flashes": [],
    }

    class FakeCapabilityResult:
        failed_players = (
            {
                "team_name": "Team One",
                "player_name": "Broken Player",
                "error": "WOM failed",
            },
        )
        profile_set = "capability-profiles"

    monkeypatch.setattr(
        admin_routes.database,
        "get_players_by_team",
        lambda: {}
    )
    monkeypatch.setattr(
        admin_routes.wom,
        "get_player",
        "fetch-player"
    )
    monkeypatch.setattr(
        admin_routes,
        "build_capability_profiles_from_rostered_players",
        lambda players_by_team, fetch_player: FakeCapabilityResult()
    )
    monkeypatch.setattr(
        admin_routes,
        "get_curated_generated_board_preview_summary",
        lambda capability_profiles=None: "generated-board-summary"
    )
    monkeypatch.setattr(
        admin_routes,
        "flash",
        lambda message, category: captured["flashes"].append(
            (
                message,
                category,
            )
        )
    )
    monkeypatch.setattr(
        admin_routes,
        "render_template",
        lambda template_name, **context: "rendered"
    )

    route_function = getattr(
        admin_routes.generated_board_preview,
        "__wrapped__",
        admin_routes.generated_board_preview
    )

    assert route_function() == "rendered"
    assert captured["flashes"] == [
        (
            "Could not fetch WOM capability data for: Broken Player.",
            "warning",
        ),
    ]
