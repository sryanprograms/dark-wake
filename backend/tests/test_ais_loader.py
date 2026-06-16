"""Tests for AIS loader helpers."""

from datetime import datetime, timezone

from app.ingest.loader import _parse_t


def test_parse_t_handles_z_suffix():
    assert _parse_t("2022-06-17T04:00:00Z") == datetime(
        2022, 6, 17, 4, 0, tzinfo=timezone.utc
    )


def test_parse_t_passes_through_datetime():
    dt = datetime(2022, 6, 17, 4, 0, tzinfo=timezone.utc)
    assert _parse_t(dt) == dt
