import hashlib
import os
import uuid


ALLOWED_EVIDENCE_EXTENSIONS = {
    '.png',
    '.jpg',
    '.jpeg',
    '.webp'
}


def _get_manual_evidence_directory():
    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    return os.path.realpath(
        os.path.join(
            project_root,
            'uploads',
            'manual_evidence'
        )
    )


def save_manual_evidence_file(
    file_bytes,
    original_filename
):
    if not isinstance(
        file_bytes,
        (bytes, bytearray)
    ) or not file_bytes:
        raise ValueError(
            "Evidence image is empty."
        )

    extension = os.path.splitext(
        original_filename or ''
    )[1].lower()

    if extension not in ALLOWED_EVIDENCE_EXTENSIONS:
        raise ValueError(
            "Evidence must be a PNG, JPG, JPEG, or WebP image."
        )

    evidence_directory = (
        _get_manual_evidence_directory()
    )

    os.makedirs(
        evidence_directory,
        exist_ok=True
    )

    file_token = uuid.uuid4().hex

    filename = (
        f'manual_evidence_'
        f'{file_token}'
        f'{extension}'
    )

    absolute_path = os.path.join(
        evidence_directory,
        filename
    )

    file_bytes = bytes(file_bytes)

    evidence_sha256 = hashlib.sha256(
        file_bytes
    ).hexdigest()

    # Exclusive creation protects against accidentally replacing an
    # existing evidence file even if a filename collision occurred.
    with open(
        absolute_path,
        'xb'
    ) as evidence_file:
        evidence_file.write(
            file_bytes
        )

    relative_path = os.path.join(
        'uploads',
        'manual_evidence',
        filename
    )

    return {
        "evidence_path": relative_path,
        "evidence_sha256": evidence_sha256
    }


def resolve_manual_evidence_path(
    evidence_path
):
    if not evidence_path:
        return None

    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    evidence_directory = (
        _get_manual_evidence_directory()
    )

    absolute_path = os.path.realpath(
        os.path.join(
            project_root,
            str(evidence_path)
        )
    )

    try:
        common_path = os.path.commonpath(
            [
                evidence_directory,
                absolute_path
            ]
        )
    except ValueError:
        return None

    if common_path != evidence_directory:
        return None

    filename = os.path.basename(
        absolute_path
    )

    filename_root, extension = os.path.splitext(
        filename
    )

    if (
        extension.lower()
        not in ALLOWED_EVIDENCE_EXTENSIONS
    ):
        return None

    prefix = 'manual_evidence_'

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


def delete_manual_evidence_file(
    evidence_path
):
    absolute_path = resolve_manual_evidence_path(
        evidence_path
    )

    if absolute_path is None:
        return False

    os.remove(
        absolute_path
    )

    return True
