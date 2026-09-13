from PIL import Image

from utils import board_renderer


def render_test_image(
    *,
    completed_coordinates=None,
    partial_coordinates=None,
    show_progress=True
):
    output = board_renderer.render_bingo_board(
        {
            "A1": "Completed Tile",
            "A2": "Partial Tile",
            "A3": "No Progress Tile"
        },
        completed_coordinates=completed_coordinates,
        partial_coordinates=partial_coordinates,
        show_progress=show_progress
    )

    return Image.open(output).convert("RGB")


def tile_centre(
    row_index,
    column_index
):
    left = (
        board_renderer.FRAME_BORDER
        + board_renderer.HEADER_SIZE
        + board_renderer.CELL_GAP
        + (
            column_index
            * (
                board_renderer.TILE_SIZE
                + board_renderer.CELL_GAP
            )
        )
    )

    top = (
        board_renderer.FRAME_BORDER
        + board_renderer.HEADER_SIZE
        + board_renderer.CELL_GAP
        + (
            row_index
            * (
                board_renderer.TILE_SIZE
                + board_renderer.CELL_GAP
            )
        )
    )

    return (
        left + (board_renderer.TILE_SIZE // 2),
        top + (board_renderer.TILE_SIZE // 2)
    )


def test_renderer_creates_expected_board_size():
    image = render_test_image()

    inner_width, inner_height = (
        board_renderer._board_inner_size()
    )

    assert image.size == (
        inner_width
        + (board_renderer.FRAME_BORDER * 2),
        inner_height
        + (board_renderer.FRAME_BORDER * 2)
    )


def test_renderer_uses_team_progress_colours():
    image = render_test_image(
        completed_coordinates={"A1"},
        partial_coordinates={"A2"}
    )

    assert image.getpixel(
        tile_centre(0, 0)
    ) == (93, 154, 80)

    assert image.getpixel(
        tile_centre(0, 1)
    ) == (225, 200, 79)

    assert image.getpixel(
        tile_centre(0, 2)
    ) == (113, 128, 141)

    assert image.getpixel(
        tile_centre(0, 3)
    ) == (38, 37, 34)


def test_clean_board_ignores_progress_colours():
    image = render_test_image(
        completed_coordinates={"A1"},
        partial_coordinates={"A2"},
        show_progress=False
    )

    expected_clean_colour = (
        113,
        128,
        141
    )

    assert image.getpixel(
        tile_centre(0, 0)
    ) == expected_clean_colour

    assert image.getpixel(
        tile_centre(0, 1)
    ) == expected_clean_colour

    assert image.getpixel(
        tile_centre(0, 2)
    ) == expected_clean_colour