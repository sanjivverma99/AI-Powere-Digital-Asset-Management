from datetime import datetime, timezone

from backend.app.services.scanner_service import is_unchanged


def test_is_unchanged_accounts_for_mongodb_millisecond_precision():
    existing = {
        "file_modified_at": datetime(
            2026,
            10,
            4,
            10,
            55,
            35,
            123000,
            tzinfo=timezone.utc,
        ),
        "size_bytes": 128,
    }

    assert is_unchanged(
        existing,
        128,
        datetime(
            2026,
            10,
            4,
            10,
            55,
            35,
            123987,
            tzinfo=timezone.utc,
        ),
    )


def test_is_unchanged_detects_changed_file_size():
    existing = {
        "file_modified_at": datetime(2026, 10, 4, tzinfo=timezone.utc),
        "size_bytes": 128,
    }

    assert not is_unchanged(
        existing,
        129,
        datetime(2026, 10, 4, tzinfo=timezone.utc),
    )
