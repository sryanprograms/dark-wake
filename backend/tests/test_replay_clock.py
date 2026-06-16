"""Tests for replay clock."""

from datetime import datetime, timedelta, timezone

from app.replay.clock import ReplayClock, in_memory_source, parse_time

FIXTURE = [
    {"mmsi": 123, "t": "2022-06-17T04:00:00Z", "lat": 59.5, "lon": 24.0},
    {"mmsi": 456, "t": "2022-06-17T04:30:00Z", "lat": 59.6, "lon": 24.1},
]


def test_parse_time_accepts_z_suffix():
    assert parse_time("2022-06-17T04:00:00Z") == datetime(
        2022, 6, 17, 4, 0, tzinfo=timezone.utc
    )


def test_replay_clock_seek_clamps_to_bounds():
    start = parse_time("2022-06-17T04:00:00Z")
    end = parse_time("2022-06-17T05:00:00Z")
    clock = ReplayClock(start=start, end=end, position_source=in_memory_source(FIXTURE))
    clock.seek("2022-06-17T10:00:00Z")
    assert clock.current == end


def test_replay_clock_tick_emits_events_in_window():
    start = parse_time("2022-06-17T04:00:00Z")
    end = parse_time("2022-06-17T05:00:00Z")
    clock = ReplayClock(start=start, end=end, position_source=in_memory_source(FIXTURE))
    clock.play()
    events = clock.tick(timedelta(minutes=45))
    assert len(events) == 2
    assert events[0]["mmsi"] == 123
