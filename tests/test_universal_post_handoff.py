"""Universal ALL POST -> PRE handoff regression tests."""

import arrow

import custom_components.teamtracker.parse_espn as parse_espn
from custom_components.teamtracker.models import TeamTrackerValues
from custom_components.teamtracker.parse_espn import EspnParser


def _parser():
    parser = EspnParser(None)
    parser.setup(
        "handoff-test",
        "soccer",
        "all",
        "ALL",
        "123",
    )
    return parser


def _values(state, event_id, date):
    return TeamTrackerValues(
        state=state,
        event_id=event_id,
        date=date,
        sport="soccer",
    )


def test_post_expires_after_24_hours_when_pre_is_far_away():
    parser = _parser()
    post_start = arrow.get("2026-09-07T10:00:00+00:00")
    pre_start = post_start.shift(days=3)

    post = _values(
        "POST",
        "post",
        post_start.shift(hours=-2).isoformat(),
    )
    pre = _values("PRE", "pre", pre_start.isoformat())

    parser._post_started_at["post"] = post_start

    assert parser._universal_keep_post(
        post,
        pre,
        now=post_start.shift(hours=23, minutes=59),
    )
    assert not parser._universal_keep_post(
        post,
        pre,
        now=post_start.shift(hours=24),
    )


def test_pre_inside_24h_uses_midpoint():
    parser = _parser()
    post_start = arrow.get("2026-09-07T10:00:00+00:00")
    pre_start = post_start.shift(hours=12)

    post = _values(
        "POST",
        "post",
        post_start.shift(hours=-2).isoformat(),
    )
    pre = _values("PRE", "pre", pre_start.isoformat())

    parser._post_started_at["post"] = post_start

    # Midpoint of 10:00 and 22:00 is 16:00.
    assert parser._universal_keep_post(
        post,
        pre,
        now=post_start.shift(hours=5, minutes=59),
    )
    assert not parser._universal_keep_post(
        post,
        pre,
        now=post_start.shift(hours=6),
    )


def test_observed_in_to_post_records_real_post_start(monkeypatch):
    parser = _parser()

    in_time = arrow.get("2026-09-07T10:00:00+00:00")
    post_time = arrow.get("2026-09-07T12:15:00+00:00")

    monkeypatch.setattr(
        parse_espn.arrow,
        "now",
        lambda: in_time,
    )

    parser._values = _values(
        "IN",
        "event-1",
        "2026-09-07T10:00:00+00:00",
    )
    parser._record_observed_event_state()

    monkeypatch.setattr(
        parse_espn.arrow,
        "now",
        lambda: post_time,
    )

    parser._values = _values(
        "POST",
        "event-1",
        "2026-09-07T10:00:00+00:00",
    )
    parser._record_observed_event_state()

    assert parser._post_started_at["event-1"] == post_time


def test_cold_start_old_post_hands_off_to_pre():
    parser = _parser()

    now = arrow.get("2026-09-08T16:00:00+00:00")

    # Soccer cold-start estimate is kickoff + 2 hours.
    post = _values(
        "POST",
        "post",
        now.shift(hours=-30).isoformat(),
    )
    pre = _values(
        "PRE",
        "pre",
        now.shift(days=4).isoformat(),
    )

    assert not parser._universal_keep_post(
        post,
        pre,
        now=now,
    )


def test_use_prev_values_flag_uses_universal_handoff(monkeypatch):
    parser = _parser()

    post_start = arrow.get("2026-09-07T10:00:00+00:00")
    now = post_start.shift(hours=25)

    monkeypatch.setattr(
        parse_espn.arrow,
        "now",
        lambda: now,
    )

    parser._prev_values = _values(
        "POST",
        "post",
        post_start.shift(hours=-2).isoformat(),
    )
    parser._values = _values(
        "PRE",
        "pre",
        post_start.shift(days=3).isoformat(),
    )
    parser._post_started_at["post"] = post_start

    assert parser._use_prev_values_flag() is False


def test_non_all_keeps_legacy_selection(monkeypatch):
    parser = EspnParser(None)
    parser.setup(
        "legacy-test",
        "soccer",
        "eng.1",
        "EPL",
        "123",
    )

    now = arrow.get("2026-09-08T16:00:00+00:00")

    monkeypatch.setattr(
        parse_espn.arrow,
        "now",
        lambda: now,
    )

    parser._prev_values = _values(
        "POST",
        "post",
        now.shift(hours=-30).isoformat(),
    )
    parser._values = _values(
        "PRE",
        "pre",
        now.shift(days=3).isoformat(),
    )

    assert parser._use_prev_values_flag() is True
