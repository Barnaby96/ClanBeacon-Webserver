from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = (
    PROJECT_ROOT
    / "templates"
    / "admin_templates"
    / "generated_board_preview.html"
)


def read_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_generated_board_preview_uses_osrs_page_layout():
    template = read_template()

    assert "css/osrs-dashboard.css" in template
    assert '<div class="osrs-dashboard generated-board-preview">' in template
    assert '<main class="osrs-page">' in template
    assert '<header class="osrs-page-header">' in template
    assert 'class="osrs-page-title"' in template
    assert 'class="osrs-page-subtitle"' in template
    assert "osrs-dashboard-header" not in template
    assert "{% block extra_head %}" not in template


def test_generated_board_preview_uses_osrs_table_classes():
    template = read_template()

    assert 'class="osrs-panel"' in template
    assert 'class="osrs-panel-header"' in template
    assert 'class="osrs-panel-body"' in template
    assert 'class="osrs-table-wrap"' in template
    assert 'class="osrs-table"' in template
    assert "generated-board-route-list" in template
    assert "generated-board-tag-list" in template
