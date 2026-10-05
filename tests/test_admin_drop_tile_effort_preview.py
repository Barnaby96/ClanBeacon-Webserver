from pathlib import Path
from types import SimpleNamespace

from routes.admin import admin_routes as admin_routes_module


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_drop_tile_effort_preview_route_renders_rows(monkeypatch):
    captured = {}

    rows = (
        SimpleNamespace(tile_mode="group_uniques"),
        SimpleNamespace(tile_mode="specific_drop"),
        SimpleNamespace(tile_mode="specific_drop"),
    )

    def fake_render_template(template_name, **context):
        captured["template_name"] = template_name
        captured["context"] = context
        return "rendered"

    monkeypatch.setattr(
        admin_routes_module,
        "build_drop_tile_effort_preview_rows",
        lambda: rows,
    )
    monkeypatch.setattr(
        admin_routes_module,
        "render_template",
        fake_render_template,
    )

    view = getattr(
        admin_routes_module.drop_tile_effort_preview,
        "__wrapped__",
        admin_routes_module.drop_tile_effort_preview,
    )

    assert view() == "rendered"
    assert captured["template_name"] == (
        "admin_templates/drop_tile_effort_preview.html"
    )
    assert captured["context"]["rows"] == rows
    assert captured["context"]["row_count"] == 3
    assert captured["context"]["counts_by_mode"] == {
        "group_uniques": 1,
        "specific_drop": 2,
    }


def test_bingo_setup_links_to_drop_tile_effort_preview():
    template = (
        PROJECT_ROOT / "templates/admin_templates/bingo_setup.html"
    ).read_text(
        encoding="utf-8"
    )

    assert "Preview Drop Effort" in template
    assert "admin_routes.drop_tile_effort_preview" in template


def test_drop_tile_effort_preview_template_contains_expected_sections():
    template = (
        PROJECT_ROOT / "templates/admin_templates/drop_tile_effort_preview.html"
    ).read_text(
        encoding="utf-8"
    )

    assert "Drop Tile Effort Preview" in template
    assert "Back to Bingo Setup" in template
    assert "Suggested points" in template
    assert "Total effort" in template
    assert "rounded for readability" in template
    assert "expected_rolls_display" in template
    assert "total_effort_display" in template
