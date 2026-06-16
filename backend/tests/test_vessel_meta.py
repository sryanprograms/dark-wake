"""Tests for MMSI flag lookup and AIS ship type labels."""

from app.ingest.vessel_meta import (
    country_from_mmsi,
    flag_from_mmsi,
    ship_type_label,
)


def test_flag_from_mmsi_finland():
    assert flag_from_mmsi(230123456) == "FI"
    assert country_from_mmsi(230123456) == "Finland"


def test_flag_from_mmsi_estonia():
    assert flag_from_mmsi(276000001) == "EE"
    assert country_from_mmsi(276000001) == "Estonia"


def test_flag_from_mmsi_unknown_mid():
    assert flag_from_mmsi(999123456) is None


def test_ship_type_label_tanker():
    assert ship_type_label(80) == "Tanker"


def test_ship_type_label_fishing():
    assert ship_type_label(30) == "Fishing"


def test_ship_type_label_zero_is_none():
    assert ship_type_label(0) is None


def test_ship_type_label_unknown_code():
    assert ship_type_label(15) == "Type 15"
