from pathlib import Path

import routes.admin.admin_routes as admin_routes


class FakeRequest:
    method = "GET"

    class form:
        @staticmethod
        def getlist(name):
            return ()


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generated_board_preview_route_renders_summary(monkeypatch):
    captured = {}

    expected_summary = object()

    class FakeCapabilityResult:
        failed_players = ()
        profile_set = "capability-profiles"

    def fake_get_summary(capability_profiles=None, kept_tile_keys=(), banned_tile_keys=()):
        captured["capability_profiles"] = capability_profiles
        captured["kept_tile_keys"] = kept_tile_keys
        captured["banned_tile_keys"] = banned_tile_keys
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
    monkeypatch.setattr(
        admin_routes,
        "request",
        FakeRequest()
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
    assert captured["kept_tile_keys"] == ()
    assert captured["banned_tile_keys"] == ()
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
    assert "summary.capability_ordering_fell_back" in template
    assert "summary.capability_ordering_fallback_reason" in template
    assert "generated-board-preview" in template
    assert 'name="current_tile_key"' in template
    assert 'name="kept_tile_key"' in template
    assert "Reroll unkept tiles" in template
    assert "Apply to Bingo Board" in template
    assert 'name="action"' in template
    assert 'value="apply_to_board"' in template
    assert "replace" in template.lower()
    assert "recorded progress" in template.lower()
    assert "or evidence" in template.lower()
    assert "row.tile_key" in template
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
        lambda capability_profiles=None, kept_tile_keys=(), banned_tile_keys=(): "generated-board-summary"
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
    monkeypatch.setattr(
        admin_routes,
        "request",
        FakeRequest()
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



def test_generated_board_preview_apply_uses_exact_current_tiles(monkeypatch):
    captured = {
        "converted_keys": None,
        "replacement_payloads": None,
        "flashes": [],
        "redirect": None,
        "url_for": None,
    }

    submitted_keys = tuple(
        f"tile-key-{index}"
        for index in range(1, 26)
    )
    expected_payloads = tuple(
        {
            "tile_name": f"Live Tile {index}",
            "tile_points": ((index - 1) // 5) + 1,
        }
        for index in range(1, 26)
    )

    class ApplyRequest:
        method = "POST"

        class form:
            @staticmethod
            def get(name, default=None):
                if name == "action":
                    return "apply_to_board"

                return default

            @staticmethod
            def getlist(name):
                if name == "current_tile_key":
                    return submitted_keys

                return ()

    def fake_build_payloads(tile_keys):
        captured["converted_keys"] = tuple(
            tile_keys
        )
        return expected_payloads

    def fake_replace_board(payloads):
        captured["replacement_payloads"] = tuple(
            payloads
        )
        return tuple(range(1, 26))

    def fake_url_for(endpoint):
        captured["url_for"] = endpoint
        return "/board/"

    def fake_redirect(location):
        captured["redirect"] = location
        return "redirected"

    monkeypatch.setattr(
        admin_routes,
        "request",
        ApplyRequest()
    )
    monkeypatch.setattr(
        admin_routes,
        "build_live_tile_payloads_from_generated_board_keys",
        fake_build_payloads,
        raising=False,
    )
    monkeypatch.setattr(
        admin_routes.database,
        "replace_bingo_board_tiles",
        fake_replace_board
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
        "url_for",
        fake_url_for
    )
    monkeypatch.setattr(
        admin_routes,
        "redirect",
        fake_redirect
    )
    monkeypatch.setattr(
        admin_routes,
        "get_current_roster_capability_profiles",
        lambda: (_ for _ in ()).throw(
            AssertionError(
                "Apply should not fetch WOM capability profiles."
            )
        )
    )

    route_function = getattr(
        admin_routes.generated_board_preview,
        "__wrapped__",
        admin_routes.generated_board_preview
    )

    assert route_function() == "redirected"
    assert captured["converted_keys"] == submitted_keys
    assert captured["replacement_payloads"] == expected_payloads
    assert captured["url_for"] == "board_routes.index"
    assert captured["redirect"] == "/board/"
    assert captured["flashes"] == [
        (
            "Generated Bingo board applied successfully.",
            "success",
        )
    ]


def test_generated_board_preview_apply_failure_preserves_preview(monkeypatch):
    captured = {
        "flashes": [],
        "kept_tile_keys": None,
        "banned_tile_keys": None,
    }

    submitted_keys = tuple(
        f"tile-key-{index}"
        for index in range(1, 26)
    )

    class ApplyRequest:
        method = "POST"

        class form:
            @staticmethod
            def get(name, default=None):
                if name == "action":
                    return "apply_to_board"

                return default

            @staticmethod
            def getlist(name):
                if name == "current_tile_key":
                    return submitted_keys

                return ()

    class FakeCapabilityResult:
        failed_players = ()
        profile_set = "capability-profiles"

    def fake_get_summary(
        capability_profiles=None,
        kept_tile_keys=(),
        banned_tile_keys=(),
    ):
        captured["kept_tile_keys"] = tuple(
            kept_tile_keys
        )
        captured["banned_tile_keys"] = tuple(
            banned_tile_keys
        )
        return "preserved-summary"

    monkeypatch.setattr(
        admin_routes,
        "request",
        ApplyRequest()
    )
    monkeypatch.setattr(
        admin_routes,
        "build_live_tile_payloads_from_generated_board_keys",
        lambda tile_keys: (
            {
                "tile_name": "Replacement Tile",
            },
        ),
    )
    monkeypatch.setattr(
        admin_routes.database,
        "replace_bingo_board_tiles",
        lambda payloads: (_ for _ in ()).throw(
            ValueError(
                "The bingo board cannot be replaced because "
                "tile 'Existing Tile' has recorded progress or evidence."
            )
        )
    )
    monkeypatch.setattr(
        admin_routes,
        "get_current_roster_capability_profiles",
        lambda: FakeCapabilityResult()
    )
    monkeypatch.setattr(
        admin_routes,
        "get_curated_generated_board_preview_summary",
        fake_get_summary
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
            "The bingo board cannot be replaced because "
            "tile 'Existing Tile' has recorded progress or evidence.",
            "danger",
        )
    ]
    assert captured["kept_tile_keys"] == submitted_keys
    assert captured["banned_tile_keys"] == ()
