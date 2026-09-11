import hashlib
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils import manual_evidence_files


def test_manual_evidence_file_can_be_saved_resolved_and_deleted():
    file_bytes = (
        b"Bingo bot manual evidence file test"
    )

    saved = None

    try:
        saved = (
            manual_evidence_files.save_manual_evidence_file(
                file_bytes=file_bytes,
                original_filename="evidence.png"
            )
        )

        assert saved["evidence_sha256"] == (
            hashlib.sha256(
                file_bytes
            ).hexdigest()
        )

        relative_path = Path(
            saved["evidence_path"]
        )

        assert relative_path.parts[0] == "uploads"
        assert relative_path.parts[1] == (
            "manual_evidence"
        )

        absolute_path = (
            manual_evidence_files
            .resolve_manual_evidence_path(
                saved["evidence_path"]
            )
        )

        assert absolute_path is not None
        assert Path(absolute_path).is_file()
        assert Path(absolute_path).read_bytes() == (
            file_bytes
        )

        assert (
            manual_evidence_files
            .delete_manual_evidence_file(
                saved["evidence_path"]
            )
            is True
        )

        assert not Path(
            absolute_path
        ).exists()

        assert (
            manual_evidence_files
            .resolve_manual_evidence_path(
                saved["evidence_path"]
            )
            is None
        )

    finally:
        if saved is not None:
            absolute_path = (
                PROJECT_ROOT
                / saved["evidence_path"]
            )

            absolute_path.unlink(
                missing_ok=True
            )


def test_manual_evidence_file_rejects_unsupported_extension():
    with pytest.raises(
        ValueError,
        match=(
            "Evidence must be a PNG, JPG, JPEG, "
            "or WebP image."
        )
    ):
        manual_evidence_files.save_manual_evidence_file(
            file_bytes=b"Not an allowed evidence file",
            original_filename="evidence.txt"
        )


def test_manual_evidence_file_resolver_rejects_unsafe_path():
    saved = None

    try:
        saved = (
            manual_evidence_files.save_manual_evidence_file(
                file_bytes=(
                    b"Manual evidence containment test"
                ),
                original_filename="evidence.webp"
            )
        )

        filename = Path(
            saved["evidence_path"]
        ).name

        unsafe_path = (
            Path("uploads")
            / "manual_evidence"
            / ".."
            / filename
        )

        assert (
            manual_evidence_files
            .resolve_manual_evidence_path(
                str(unsafe_path)
            )
            is None
        )

        assert (
            manual_evidence_files
            .delete_manual_evidence_file(
                str(unsafe_path)
            )
            is False
        )

        # The genuine evidence file must still exist.
        genuine_path = (
            manual_evidence_files
            .resolve_manual_evidence_path(
                saved["evidence_path"]
            )
        )

        assert genuine_path is not None
        assert Path(genuine_path).is_file()

    finally:
        if saved is not None:
            manual_evidence_files.delete_manual_evidence_file(
                saved["evidence_path"]
            )
