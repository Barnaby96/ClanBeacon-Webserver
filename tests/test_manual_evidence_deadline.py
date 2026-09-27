import pytest

from utils import database


def _call_add_manual_evidence(**overrides):
    kwargs = {
        "player_id": 1,
        "condition_id": 1,
        "amount": 1,
        "evidence_path": "manual-evidence/example.png",
        "evidence_sha256": "a" * 64,
        "submission_source": "WEB",
        "submitter_id": 1,
        "submitter_name": "Test Submitter",
    }

    kwargs.update(overrides)

    return database.add_manual_evidence(**kwargs)


def test_manual_evidence_blocks_normal_submission_after_wom_end(monkeypatch):
    monkeypatch.setattr(
        database,
        "is_wom_competition_ended",
        lambda: True
    )

    with pytest.raises(ValueError) as error:
        _call_add_manual_evidence()

    assert "WOM competition has ended" in str(error.value)


def test_manual_evidence_after_end_override_skips_deadline_gate(monkeypatch):
    monkeypatch.setattr(
        database,
        "is_wom_competition_ended",
        lambda: True
    )

    with pytest.raises(ValueError) as error:
        _call_add_manual_evidence(
            evidence_path="",
            submission_source="DISCORD",
            allow_after_competition_end=True
        )

    assert "WOM competition has ended" not in str(error.value)
