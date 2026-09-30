from pathlib import Path

import routes.admin.admin_routes as admin_routes


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generated_board_preview_route_renders_summary(monkeypatch):
    captured = {}

    expected_summary = object()

    monkeypatch.setattr(
        admin_routes,
        "get_curated_generated_board_preview_summary",
        lambda: expected_summary
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
    assert "summary.rows_by_point_value.items()" in template
    assert "summary.counts_by_point_value.items()" in template
    assert "summary.counts_by_primary_category.items()" in template
    assert "generated-board-preview" in template
    assert "color: #2b1a0b;" in template
