"""
Tests for unifi-family's pure logic (no network, no live controller).

Run with uv:
    uv run --with pytest pytest
or:
    uv run --with pytest python -m pytest -q
"""
import importlib.util
import importlib.machinery
import pathlib
import types

import pytest

# Load the hyphenated, extensionless script as a module.
_PATH = pathlib.Path(__file__).resolve().parent.parent / "unifi-family"
_loader = importlib.machinery.SourceFileLoader("unifi_family", str(_PATH))
_spec = importlib.util.spec_from_loader("unifi_family", _loader)
uf = importlib.util.module_from_spec(_spec)
_loader.exec_module(uf)


def sched_args(**kw):
    """Build a namespace with the scheduling attributes build_schedule reads."""
    base = dict(start=None, stop=None, days=None, date=None,
                start_date=None, stop_date=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


# --------------------------------------------------------------------------- #
# _parse_days
# --------------------------------------------------------------------------- #
def test_parse_days_aliases_and_order():
    assert uf._parse_days("fri,mon,wed") == ["MONDAY", "WEDNESDAY", "FRIDAY"]


def test_parse_days_keywords():
    assert uf._parse_days("weekdays") == uf.DAY_NAMES[:5]
    assert uf._parse_days("weekends") == uf.DAY_NAMES[5:]
    assert uf._parse_days("everyday") == uf.DAY_NAMES
    assert uf._parse_days("daily") == uf.DAY_NAMES


def test_parse_days_dedupes():
    assert uf._parse_days("mon,mon,monday") == ["MONDAY"]


def test_parse_days_full_names_case_insensitive():
    assert uf._parse_days("TUESDAY,sun") == ["TUESDAY", "SUNDAY"]


def test_parse_days_invalid_exits():
    with pytest.raises(SystemExit):
        uf._parse_days("funday")


# --------------------------------------------------------------------------- #
# build_schedule
# --------------------------------------------------------------------------- #
def test_build_schedule_none():
    assert uf.build_schedule(sched_args()) is None


def test_build_schedule_every_day_window():
    s = uf.build_schedule(sched_args(start="20:00", stop="07:00"))
    assert s == {"mode": "EVERY_DAY",
                 "timeFilter": {"startTime": "20:00", "stopTime": "07:00"}}


def test_build_schedule_every_week_with_and_without_time():
    s = uf.build_schedule(sched_args(days="weekdays"))
    assert s["mode"] == "EVERY_WEEK"
    assert s["repeatOnDays"] == uf.DAY_NAMES[:5]
    assert "timeFilter" not in s

    s2 = uf.build_schedule(sched_args(days="sat,sun", start="08:00", stop="10:00"))
    assert s2["repeatOnDays"] == ["SATURDAY", "SUNDAY"]
    assert s2["timeFilter"] == {"startTime": "08:00", "stopTime": "10:00"}


def test_build_schedule_one_time():
    s = uf.build_schedule(sched_args(date="2026-12-25"))
    assert s["mode"] == "ONE_TIME_ONLY"
    assert s["date"] == "2026-12-25"
    # defaults to all-day when no window given
    assert s["timeFilter"] == {"startTime": "00:00", "stopTime": "23:59"}


def test_build_schedule_custom_range_defaults_all_days():
    s = uf.build_schedule(sched_args(start_date="2026-12-01", stop_date="2026-12-15"))
    assert s["mode"] == "CUSTOM"
    assert s["repeatOnDays"] == uf.DAY_NAMES
    assert "timeFilter" not in s


def test_build_schedule_custom_range_with_days_and_time():
    s = uf.build_schedule(sched_args(start_date="2026-12-01", stop_date="2026-12-15",
                                     days="weekdays", start="16:00", stop="18:00"))
    assert s["repeatOnDays"] == uf.DAY_NAMES[:5]
    assert s["timeFilter"]["startTime"] == "16:00"


def test_build_schedule_requires_both_times():
    with pytest.raises(SystemExit):
        uf.build_schedule(sched_args(start="20:00"))


def test_build_schedule_requires_both_dates():
    with pytest.raises(SystemExit):
        uf.build_schedule(sched_args(start_date="2026-12-01"))


# --------------------------------------------------------------------------- #
# _fmt_schedule
# --------------------------------------------------------------------------- #
def test_fmt_schedule_always():
    assert uf._fmt_schedule(None) == "always"


def test_fmt_schedule_every_day():
    s = {"mode": "EVERY_DAY", "timeFilter": {"startTime": "20:00", "stopTime": "07:00"}}
    assert uf._fmt_schedule(s) == "daily 20:00–07:00"


def test_fmt_schedule_weekdays_label():
    s = {"mode": "EVERY_WEEK", "repeatOnDays": uf.DAY_NAMES[:5]}
    assert uf._fmt_schedule(s) == "weekdays"


def test_fmt_schedule_weekends_label():
    s = {"mode": "EVERY_WEEK", "repeatOnDays": ["SATURDAY", "SUNDAY"]}
    assert uf._fmt_schedule(s) == "weekends"


def test_fmt_schedule_custom_days_normalized_order():
    # out-of-order input should render in week order with short names
    s = {"mode": "EVERY_WEEK", "repeatOnDays": ["FRIDAY", "MONDAY", "WEDNESDAY"]}
    assert uf._fmt_schedule(s) == "Mon,Wed,Fri"


def test_fmt_schedule_one_time():
    s = {"mode": "ONE_TIME_ONLY", "date": "2026-12-25",
         "timeFilter": {"startTime": "00:00", "stopTime": "23:59"}}
    assert uf._fmt_schedule(s) == "on 2026-12-25 00:00–23:59"


def test_fmt_schedule_custom_range():
    s = {"mode": "CUSTOM", "startDate": "2026-12-01", "stopDate": "2026-12-15",
         "repeatOnDays": uf.DAY_NAMES}
    assert uf._fmt_schedule(s) == "2026-12-01→2026-12-15 daily"


# --------------------------------------------------------------------------- #
# _source_matches_mac
# --------------------------------------------------------------------------- #
def test_source_matches_no_filter_is_all():
    assert uf._source_matches_mac({}, "aa:bb:cc:dd:ee:ff") == "all"


def test_source_matches_mac_yes_no():
    src = {"trafficFilter": {"type": "MAC_ADDRESS",
                             "macAddressFilter": {"macAddresses": ["AA:BB:CC:DD:EE:FF"]}}}
    assert uf._source_matches_mac(src, "aa:bb:cc:dd:ee:ff") == "yes"
    assert uf._source_matches_mac(src, "11:22:33:44:55:66") == "no"


def test_source_matches_network_whole_is_all():
    src = {"trafficFilter": {"type": "NETWORK", "networkFilter": {"networkIds": ["x"]}}}
    assert uf._source_matches_mac(src, "aa:bb:cc:dd:ee:ff") == "all"


def test_source_matches_network_with_mac():
    src = {"trafficFilter": {"type": "NETWORK", "networkFilter": {},
                             "macAddressFilter": "AA:BB:CC:DD:EE:FF"}}
    assert uf._source_matches_mac(src, "aa:bb:cc:dd:ee:ff") == "yes"
    assert uf._source_matches_mac(src, "00:00:00:00:00:00") == "no"


# --------------------------------------------------------------------------- #
# pick_zone
# --------------------------------------------------------------------------- #
def test_pick_zone_exact_then_substring():
    zones = [{"name": "Internal", "id": "1"}, {"name": "External", "id": "2"}]
    assert uf.pick_zone(zones, "internal")["id"] == "1"
    assert uf.pick_zone(zones, "ext")["id"] == "2"
    assert uf.pick_zone(zones, "Dmz") is None


# --------------------------------------------------------------------------- #
# _strip_for_put / _policy_domains
# --------------------------------------------------------------------------- #
def test_strip_for_put_removes_readonly():
    p = {"id": "x", "index": 5, "metadata": {"origin": "USER_DEFINED"},
         "name": "keep", "enabled": True}
    out = uf._strip_for_put(p)
    assert out == {"name": "keep", "enabled": True}


def test_policy_domains_valid():
    p = {"destination": {"trafficFilter": {"type": "DOMAIN",
         "domainFilter": {"type": "DOMAINS", "domains": ["a.com"]}}}}
    df = uf._policy_domains(p)
    assert df["domains"] == ["a.com"]


def test_policy_domains_wrong_type_exits():
    p = {"destination": {"trafficFilter": {"type": "APPLICATION_CATEGORY",
         "applicationCategoryFilter": {"applicationCategoryIds": [1]}}}}
    with pytest.raises(SystemExit):
        uf._policy_domains(p)


# --------------------------------------------------------------------------- #
# resolve_macs (member-aware); no network for member / raw-MAC paths
# --------------------------------------------------------------------------- #
MEMBERS = {
    "alex": {"group": "kid", "devices": [
        {"mac": "AA:BB:CC:00:00:01", "name": "Alex Laptop"},
        {"mac": "AA:BB:CC:00:00:02", "name": "Alex Phone"},
    ]},
    "robin": {"group": "adult", "devices": []},
}


def test_resolve_macs_member_expands_all(monkeypatch):
    monkeypatch.setattr(uf, "load_members", lambda: MEMBERS)
    out = uf.resolve_macs(None, None, "alex")
    assert [m for m, _ in out] == ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"]


def test_resolve_macs_member_device_filter(monkeypatch):
    monkeypatch.setattr(uf, "load_members", lambda: MEMBERS)
    out = uf.resolve_macs(None, None, "alex:phone")
    assert [m for m, _ in out] == ["aa:bb:cc:00:00:02"]


def test_resolve_macs_member_filter_no_match_exits(monkeypatch):
    monkeypatch.setattr(uf, "load_members", lambda: MEMBERS)
    with pytest.raises(SystemExit):
        uf.resolve_macs(None, None, "alex:tablet")


def test_resolve_macs_member_without_devices_exits(monkeypatch):
    monkeypatch.setattr(uf, "load_members", lambda: MEMBERS)
    with pytest.raises(SystemExit):
        uf.resolve_macs(None, None, "robin")


def test_resolve_macs_raw_mac(monkeypatch):
    monkeypatch.setattr(uf, "load_members", lambda: {})
    out = uf.resolve_macs(None, None, "AA:BB:CC:DD:EE:FF")
    assert out == [("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff")]


def test_resolve_macs_allow_member_false_skips_members(monkeypatch):
    monkeypatch.setattr(uf, "load_members", lambda: MEMBERS)
    # a raw MAC still resolves even with allow_member False
    out = uf.resolve_macs(None, None, "AA:BB:CC:DD:EE:FF", allow_member=False)
    assert out == [("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff")]


# --------------------------------------------------------------------------- #
# Config URL building (cloud connector vs local console)
# --------------------------------------------------------------------------- #
def make_cfg(monkeypatch, **kw):
    # Isolate from the real ~/.config/unifi/config.json and env vars.
    monkeypatch.setattr(uf, "CONFIG_PATH", pathlib.Path("/nonexistent/unifi/config.json"))
    for v in ("UNIFI_BASE_URL", "UNIFI_API_KEY", "UNIFI_SITE"):
        monkeypatch.delenv(v, raising=False)
    args = types.SimpleNamespace(base_url=kw.get("base_url"), api_key="k",
                                 site=kw.get("site"), verify_tls=None,
                                 console_id=kw.get("console_id"))
    return uf.Config(args)


def test_config_local_url(monkeypatch):
    cfg = make_cfg(monkeypatch, base_url="https://192.168.4.1")
    assert cfg.url("/v1/sites") == "https://192.168.4.1/proxy/network/integration/v1/sites"
    assert cfg.legacy_url("/s/default/stat/sta") == \
        "https://192.168.4.1/proxy/network/api/s/default/stat/sta"


def test_config_cloud_url(monkeypatch):
    cfg = make_cfg(monkeypatch, base_url="https://api.ui.com", console_id="CID")
    assert cfg.url("/v1/sites") == \
        "https://api.ui.com/v1/connector/consoles/CID/proxy/network/integration/v1/sites"
    assert cfg.legacy_url("/s/default/stat/sta") == \
        "https://api.ui.com/v1/connector/consoles/CID/proxy/network/api/s/default/stat/sta"
