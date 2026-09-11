import os
import uuid


ALLOWED_TEAM_PHOTO_EXTENSIONS = {
    '.png',
    '.jpg',
    '.jpeg',
    '.webp'
}

MAX_TEAM_PHOTO_BYTES = 10 * 1024 * 1024


def _get_team_photo_directory():
    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    return os.path.realpath(
        os.path.join(
            project_root,
            'uploads',
            'team_photos'
        )
    )


def _detect_image_format(file_bytes):
    if file_bytes.startswith(
        b'\x89PNG\r\n\x1a\n'
    ):
        return 'png'

    if file_bytes.startswith(
        b'\xff\xd8\xff'
    ):
        return 'jpeg'

    if (
        len(file_bytes) >= 12
        and file_bytes[0:4] == b'RIFF'
        and file_bytes[8:12] == b'WEBP'
    ):
        return 'webp'

    return None


def save_team_photo_file(
    file_bytes,
    original_filename
):
    if not isinstance(
        file_bytes,
        (bytes, bytearray)
    ) or not file_bytes:
        raise ValueError(
            "Team photo is empty."
        )

    file_bytes = bytes(file_bytes)

    if len(file_bytes) > MAX_TEAM_PHOTO_BYTES:
        raise ValueError(
            "Team photo must be 10 MB or smaller."
        )

    extension = os.path.splitext(
        original_filename or ''
    )[1].lower()

    if extension not in ALLOWED_TEAM_PHOTO_EXTENSIONS:
        raise ValueError(
            "Team photo must be a PNG, JPG, JPEG, or WebP image."
        )

    detected_format = _detect_image_format(
        file_bytes
    )

    if detected_format is None:
        raise ValueError(
            "Team photo is not a recognised PNG, JPG, JPEG, "
            "or WebP image."
        )

    extension_matches = {
        'png': {
            '.png'
        },
        'jpeg': {
            '.jpg',
            '.jpeg'
        },
        'webp': {
            '.webp'
        }
    }

    if extension not in extension_matches[
        detected_format
    ]:
        raise ValueError(
            "Team photo file extension does not match "
            "the image format."
        )

    photo_directory = (
        _get_team_photo_directory()
    )

    os.makedirs(
        photo_directory,
        exist_ok=True
    )

    file_token = uuid.uuid4().hex

    filename = (
        f'team_photo_'
        f'{file_token}'
        f'{extension}'
    )

    absolute_path = os.path.join(
        photo_directory,
        filename
    )

    with open(
        absolute_path,
        'xb'
    ) as photo_file:
        photo_file.write(
            file_bytes
        )

    return os.path.join(
        'uploads',
        'team_photos',
        filename
    )


def resolve_team_photo_path(
    photo_path
):
    if not photo_path:
        return None

    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    photo_directory = (
        _get_team_photo_directory()
    )

    absolute_path = os.path.realpath(
        os.path.join(
            project_root,
            str(photo_path)
        )
    )

    try:
        common_path = os.path.commonpath(
            [
                photo_directory,
                absolute_path
            ]
        )
    except ValueError:
        return None

    if common_path != photo_directory:
        return None

    filename = os.path.basename(
        absolute_path
    )

    filename_root, extension = os.path.splitext(
        filename
    )

    if extension.lower() not in ALLOWED_TEAM_PHOTO_EXTENSIONS:
        return None

    prefix = 'team_photo_'

    if not filename_root.startswith(
        prefix
    ):
        return None

    file_token = filename_root[
        len(prefix):
    ]

    try:
        parsed_token = uuid.UUID(
            hex=file_token
        )
    except (ValueError, AttributeError):
        return None

    if parsed_token.hex != file_token.lower():
        return None

    if not os.path.isfile(
        absolute_path
    ):
        return None

    return absolute_path


def delete_team_photo_file(
    photo_path
):
    absolute_path = resolve_team_photo_path(
        photo_path
    )

    if absolute_path is None:
        return False

    os.remove(
        absolute_path
    )

    return True