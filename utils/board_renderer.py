from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FRAME_PATH = (
    PROJECT_ROOT
    / "static"
    / "images"
    / "bingo_board"
    / "board_frame.png"
)

BOLD_FONT_PATH = (
    PROJECT_ROOT
    / "static"
    / "fonts"
    / "RuneScape-Bold-12.ttf"
)

BOARD_ROWS = ("A", "B", "C", "D", "E")
BOARD_COLUMNS = (1, 2, 3, 4, 5)

FRAME_SOURCE_SLICE = 125
FRAME_BORDER = 72

HEADER_SIZE = 54
TILE_SIZE = 176
CELL_GAP = 4

BOARD_BACKGROUND = "#171512"
HEADER_BACKGROUND = "#302e2b"
HEADER_TEXT = "#f1d06a"

COMPLETE_BACKGROUND = "#5d9a50"
COMPLETE_TEXT = "#fff4d2"

PARTIAL_BACKGROUND = "#e1c84f"
PARTIAL_TEXT = "#211a08"

INCOMPLETE_BACKGROUND = "#71808d"
INCOMPLETE_TEXT = "#f4f0e5"

EMPTY_BACKGROUND = "#262522"

CELL_BORDER = "#171512"
CELL_HIGHLIGHT = "#ffffff"
CELL_SHADOW = "#000000"

COORDINATE_TEXT = "#d9d3c7"


def _board_inner_size():
    dimension = (
        HEADER_SIZE
        + (CELL_GAP * len(BOARD_COLUMNS))
        + (TILE_SIZE * len(BOARD_COLUMNS))
    )

    return dimension, dimension


def _draw_nine_slice_frame(
    destination,
    frame_source,
    inner_width,
    inner_height
):
    source_width, source_height = frame_source.size

    source_slice = FRAME_SOURCE_SLICE
    border = FRAME_BORDER

    outer_width = inner_width + (border * 2)
    outer_height = inner_height + (border * 2)

    top_left = frame_source.crop(
        (
            0,
            0,
            source_slice,
            source_slice
        )
    )

    top = frame_source.crop(
        (
            source_slice,
            0,
            source_width - source_slice,
            source_slice
        )
    )

    top_right = frame_source.crop(
        (
            source_width - source_slice,
            0,
            source_width,
            source_slice
        )
    )

    left = frame_source.crop(
        (
            0,
            source_slice,
            source_slice,
            source_height - source_slice
        )
    )

    right = frame_source.crop(
        (
            source_width - source_slice,
            source_slice,
            source_width,
            source_height - source_slice
        )
    )

    bottom_left = frame_source.crop(
        (
            0,
            source_height - source_slice,
            source_slice,
            source_height
        )
    )

    bottom = frame_source.crop(
        (
            source_slice,
            source_height - source_slice,
            source_width - source_slice,
            source_height
        )
    )

    bottom_right = frame_source.crop(
        (
            source_width - source_slice,
            source_height - source_slice,
            source_width,
            source_height
        )
    )

    destination.alpha_composite(
        top_left.resize(
            (border, border)
        ),
        (0, 0)
    )

    destination.alpha_composite(
        top.resize(
            (inner_width, border)
        ),
        (border, 0)
    )

    destination.alpha_composite(
        top_right.resize(
            (border, border)
        ),
        (border + inner_width, 0)
    )

    destination.alpha_composite(
        left.resize(
            (border, inner_height)
        ),
        (0, border)
    )

    destination.alpha_composite(
        right.resize(
            (border, inner_height)
        ),
        (border + inner_width, border)
    )

    destination.alpha_composite(
        bottom_left.resize(
            (border, border)
        ),
        (0, border + inner_height)
    )

    destination.alpha_composite(
        bottom.resize(
            (inner_width, border)
        ),
        (border, border + inner_height)
    )

    destination.alpha_composite(
        bottom_right.resize(
            (border, border)
        ),
        (border + inner_width, border + inner_height)
    )

    return outer_width, outer_height


def _text_width(
    draw,
    text,
    font
):
    left, _, right, _ = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    return right - left


def _split_long_word(
    draw,
    word,
    font,
    max_width
):
    parts = []
    current = ""

    for character in word:
        candidate = current + character

        if (
            current
            and _text_width(
                draw,
                candidate,
                font
            ) > max_width
        ):
            parts.append(current)
            current = character
        else:
            current = candidate

    if current:
        parts.append(current)

    return parts


def _wrap_text(
    draw,
    text,
    font,
    max_width
):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        if _text_width(
            draw,
            word,
            font
        ) > max_width:
            word_parts = _split_long_word(
                draw,
                word,
                font,
                max_width
            )
        else:
            word_parts = [word]

        for part in word_parts:
            candidate = (
                part
                if not current_line
                else f"{current_line} {part}"
            )

            if (
                current_line
                and _text_width(
                    draw,
                    candidate,
                    font
                ) > max_width
            ):
                lines.append(current_line)
                current_line = part
            else:
                current_line = candidate

    if current_line:
        lines.append(current_line)

    return lines


def _fit_tile_text(
    draw,
    text
):
    max_width = TILE_SIZE - 22
    max_height = TILE_SIZE - 42

    for font_size in range(
        30,
        15,
        -2
    ):
        font = ImageFont.truetype(
            BOLD_FONT_PATH,
            font_size
        )

        lines = _wrap_text(
            draw,
            text,
            font,
            max_width
        )

        line_box = draw.textbbox(
            (0, 0),
            "Ag",
            font=font
        )

        line_height = (
            line_box[3]
            - line_box[1]
            + 4
        )

        total_height = (
            len(lines)
            * line_height
        )

        if (
            len(lines) <= 5
            and total_height <= max_height
        ):
            return font, lines, line_height

    font = ImageFont.truetype(
        BOLD_FONT_PATH,
        16
    )

    lines = _wrap_text(
        draw,
        text,
        font,
        max_width
    )

    line_box = draw.textbbox(
        (0, 0),
        "Ag",
        font=font
    )

    line_height = (
        line_box[3]
        - line_box[1]
        + 4
    )

    return (
        font,
        lines[:5],
        line_height
    )


def _draw_cell(
    draw,
    box,
    background
):
    left, top, right, bottom = box

    draw.rectangle(
        box,
        fill=background,
        outline=CELL_BORDER,
        width=3
    )

    draw.line(
        (
            left + 3,
            top + 3,
            right - 3,
            top + 3
        ),
        fill=CELL_HIGHLIGHT,
        width=1
    )

    draw.line(
        (
            left + 3,
            top + 3,
            left + 3,
            bottom - 3
        ),
        fill=CELL_HIGHLIGHT,
        width=1
    )

    draw.line(
        (
            left + 3,
            bottom - 3,
            right - 3,
            bottom - 3
        ),
        fill=CELL_SHADOW,
        width=2
    )

    draw.line(
        (
            right - 3,
            top + 3,
            right - 3,
            bottom - 3
        ),
        fill=CELL_SHADOW,
        width=2
    )


def _draw_header_text(
    draw,
    box,
    text,
    font
):
    left, top, right, bottom = box

    text_box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = (
        text_box[2]
        - text_box[0]
    )

    text_height = (
        text_box[3]
        - text_box[1]
    )

    x = (
        left
        + ((right - left - text_width) / 2)
    )

    y = (
        top
        + ((bottom - top - text_height) / 2)
        - text_box[1]
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=HEADER_TEXT
    )


def render_bingo_board(
    tile_names_by_coordinate,
    *,
    completed_coordinates=None,
    partial_coordinates=None,
    show_progress=True
):
    completed_coordinates = set(
        completed_coordinates or []
    )

    partial_coordinates = set(
        partial_coordinates or []
    )

    inner_width, inner_height = (
        _board_inner_size()
    )

    outer_width = (
        inner_width
        + (FRAME_BORDER * 2)
    )

    outer_height = (
        inner_height
        + (FRAME_BORDER * 2)
    )

    image = Image.new(
        "RGBA",
        (
            outer_width,
            outer_height
        ),
        (0, 0, 0, 0)
    )

    frame_source = Image.open(
        FRAME_PATH
    ).convert(
        "RGBA"
    )

    _draw_nine_slice_frame(
        image,
        frame_source,
        inner_width,
        inner_height
    )

    draw = ImageDraw.Draw(
        image
    )

    content_left = FRAME_BORDER
    content_top = FRAME_BORDER

    draw.rectangle(
        (
            content_left,
            content_top,
            content_left + inner_width,
            content_top + inner_height
        ),
        fill=BOARD_BACKGROUND
    )

    header_font = ImageFont.truetype(
        BOLD_FONT_PATH,
        30
    )

    coordinate_font = ImageFont.truetype(
        BOLD_FONT_PATH,
        18
    )

    corner_box = (
        content_left,
        content_top,
        content_left + HEADER_SIZE,
        content_top + HEADER_SIZE
    )

    _draw_cell(
        draw,
        corner_box,
        HEADER_BACKGROUND
    )

    for column_index, column in enumerate(
        BOARD_COLUMNS
    ):
        left = (
            content_left
            + HEADER_SIZE
            + CELL_GAP
            + (
                column_index
                * (
                    TILE_SIZE
                    + CELL_GAP
                )
            )
        )

        top = content_top

        box = (
            left,
            top,
            left + TILE_SIZE,
            top + HEADER_SIZE
        )

        _draw_cell(
            draw,
            box,
            HEADER_BACKGROUND
        )

        _draw_header_text(
            draw,
            box,
            str(column),
            header_font
        )

    for row_index, row in enumerate(
        BOARD_ROWS
    ):
        top = (
            content_top
            + HEADER_SIZE
            + CELL_GAP
            + (
                row_index
                * (
                    TILE_SIZE
                    + CELL_GAP
                )
            )
        )

        header_box = (
            content_left,
            top,
            content_left + HEADER_SIZE,
            top + TILE_SIZE
        )

        _draw_cell(
            draw,
            header_box,
            HEADER_BACKGROUND
        )

        _draw_header_text(
            draw,
            header_box,
            row,
            header_font
        )

        for column_index, column in enumerate(
            BOARD_COLUMNS
        ):
            coordinate = (
                f"{row}{column}"
            )

            left = (
                content_left
                + HEADER_SIZE
                + CELL_GAP
                + (
                    column_index
                    * (
                        TILE_SIZE
                        + CELL_GAP
                    )
                )
            )

            box = (
                left,
                top,
                left + TILE_SIZE,
                top + TILE_SIZE
            )

            tile_name = (
                tile_names_by_coordinate.get(
                    coordinate
                )
            )

            if tile_name is None:
                _draw_cell(
                    draw,
                    box,
                    EMPTY_BACKGROUND
                )
                continue

            if not show_progress:
                background = (
                    INCOMPLETE_BACKGROUND
                )
                text_colour = (
                    INCOMPLETE_TEXT
                )
            elif coordinate in completed_coordinates:
                background = (
                    COMPLETE_BACKGROUND
                )
                text_colour = (
                    COMPLETE_TEXT
                )
            elif coordinate in partial_coordinates:
                background = (
                    PARTIAL_BACKGROUND
                )
                text_colour = (
                    PARTIAL_TEXT
                )
            else:
                background = (
                    INCOMPLETE_BACKGROUND
                )
                text_colour = (
                    INCOMPLETE_TEXT
                )

            _draw_cell(
                draw,
                box,
                background
            )

            font, lines, line_height = (
                _fit_tile_text(
                    draw,
                    tile_name
                )
            )

            total_text_height = (
                len(lines)
                * line_height
            )

            text_y = (
                top
                + (
                    (
                        TILE_SIZE
                        - total_text_height
                    )
                    / 2
                )
                - 4
            )

            for line in lines:
                text_box = draw.textbbox(
                    (0, 0),
                    line,
                    font=font
                )

                text_width = (
                    text_box[2]
                    - text_box[0]
                )

                text_x = (
                    left
                    + (
                        (
                            TILE_SIZE
                            - text_width
                        )
                        / 2
                    )
                )

                draw.text(
                    (
                        text_x,
                        text_y
                    ),
                    line,
                    font=font,
                    fill=text_colour
                )

                text_y += line_height

            draw.text(
                (
                    left + 8,
                    top + TILE_SIZE - 23
                ),
                coordinate,
                font=coordinate_font,
                fill=COORDINATE_TEXT
            )

    output = BytesIO()

    image.convert(
        "RGB"
    ).save(
        output,
        format="PNG",
        optimize=True
    )

    output.seek(0)

    return output