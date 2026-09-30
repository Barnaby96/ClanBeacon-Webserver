from pathlib import Path

from routes.admin import admin_routes as admin_routes_module


def test_tile_catalogue_preview_route_renders_summary(monkeypatch):
    captured = {}

    def fake_get_summary():
        return "catalogue-summary"

    def fake_render_template(template_name, **context):
        captured["template_name"] = template_name
        captured["context"] = context
        return "rendered"

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
    assert "summary.conflicts" in template
    assert "tile-catalogue-preview" in template
    assert "color: #2b1a0b;" in template
