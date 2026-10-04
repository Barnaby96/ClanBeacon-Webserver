from pathlib import Path

from routes.admin import admin_routes as admin_routes_module


def test_tile_catalogue_preview_route_renders_summary(monkeypatch):
    captured = {}

    class FakeCapabilityResult:
        failed_players = ()
        profile_set = "capability-profiles"

    def fake_get_summary(capability_profiles=None):
        captured["capability_profiles"] = capability_profiles
        return "catalogue-summary"

    def fake_build_capability_profiles(players_by_team, fetch_player):
        captured["players_by_team"] = players_by_team
        captured["fetch_player"] = fetch_player
        return FakeCapabilityResult()

    def fake_render_template(template_name, **context):
        captured["template_name"] = template_name
        captured["context"] = context
        return "rendered"

    monkeypatch.setattr(
        admin_routes_module.database,
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
        admin_routes_module.wom,
        "get_player",
        "fetch-player"
    )
    monkeypatch.setattr(
        admin_routes_module,
        "build_capability_profiles_from_rostered_players",
        fake_build_capability_profiles
    )
    monkeypatch.setattr(
        admin_routes_module,
        "get_curated_tile_catalogue_summary",
        fake_get_summary
    )
    monkeypatch.setattr(
        admin_routes_module,
        "render_template",
        fake_render_template
    )

    view = getattr(
        admin_routes_module.tile_catalogue_preview,
        "__wrapped__",
        admin_routes_module.tile_catalogue_preview
    )

    result = view()

    assert result == "rendered"
    assert captured["template_name"] == "admin_templates/tile_catalogue_preview.html"
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
    assert captured["context"] == {
        "summary": "catalogue-summary",
    }


def test_bingo_setup_links_to_tile_catalogue_preview():
    template = Path(
        "../templates/admin_templates/bingo_setup.html"
    ).read_text(
        encoding="utf-8"
    )

    assert "Board Generation Tools" in template
    assert "Preview Tile Catalogue" in template
    assert "admin_routes.tile_catalogue_preview" in template


def test_tile_catalogue_preview_template_links_back_to_bingo_setup():
    template = Path(
        "../templates/admin_templates/tile_catalogue_preview.html"
    ).read_text(
        encoding="utf-8"
    )

    assert "Tile Catalogue Preview" in template
    assert "Back to Bingo Setup" in template
    assert "admin_routes.bingo_setup" in template
    assert "summary.requirement_summaries" in template
    assert "Capability" in template
    assert "candidate.capability_summary_text" in template
    assert "candidate.capability_warning_level" in template
    assert "summary.conflicts" in template
    assert "tile-catalogue-preview" in template
    assert "color: #2b1a0b;" in template


def test_tile_catalogue_preview_route_flashes_wom_failures(monkeypatch):
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
        admin_routes_module.database,
        "get_players_by_team",
        lambda: {}
    )
    monkeypatch.setattr(
        admin_routes_module.wom,
        "get_player",
        "fetch-player"
    )
    monkeypatch.setattr(
        admin_routes_module,
        "build_capability_profiles_from_rostered_players",
        lambda players_by_team, fetch_player: FakeCapabilityResult()
    )
    monkeypatch.setattr(
        admin_routes_module,
        "get_curated_tile_catalogue_summary",
        lambda capability_profiles=None: "catalogue-summary"
    )
    monkeypatch.setattr(
        admin_routes_module,
        "flash",
        lambda message, category: captured["flashes"].append(
            (
                message,
                category,
            )
        )
    )
    monkeypatch.setattr(
        admin_routes_module,
        "render_template",
        lambda template_name, **context: "rendered"
    )

    view = getattr(
        admin_routes_module.tile_catalogue_preview,
        "__wrapped__",
        admin_routes_module.tile_catalogue_preview
    )

    result = view()

    assert result == "rendered"
    assert captured["flashes"] == [
        (
            "Could not fetch WOM capability data for: Broken Player.",
            "warning",
        ),
    ]
