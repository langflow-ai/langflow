"""Unit tests for --axes / --suite selection and composition."""

from __future__ import annotations

import pytest

from tests.locust.langflow_runtime.config.selection import (
    STRESS_AXES,
    compose_axes_profile,
    load_suites_catalog,
    parse_axes,
    resolve_selection,
    resolve_suite_axes,
    solo_population,
)
from tests.locust.langflow_runtime.users.registry import USER_REGISTRY


def test_parse_axes_normalizes_order_and_dedupes() -> None:
    assert parse_axes("cpu_graph,chat_db,cpu_graph") == ["chat_db", "cpu_graph"]


def test_parse_axes_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown stress axis"):
        parse_axes("chat_db,not_an_axis")


def test_compose_single_axis_matches_solo_user() -> None:
    profile = compose_axes_profile(["chat_db"])
    assert profile.movement_kind == "axis_set"
    assert profile.id == "chat_db"
    assert [e.user_class for e in profile.workload.user_mix] == ["ChatDbUser"]


def test_compose_multi_axis_merges_user_mix() -> None:
    profile = compose_axes_profile(["chat_db", "cpu_graph"])
    classes = [e.user_class for e in profile.workload.user_mix]
    assert classes == ["ChatDbUser", "CpuGraphUser"]
    assert set(profile.stress_categories) >= {"chat_db", "cpu_graph"}
    for name in classes:
        assert name in USER_REGISTRY


def test_compose_chat_db_queue_gives_each_class_population() -> None:
    profile = compose_axes_profile(["chat_db", "queue"])
    assert profile.workload.workload_model == "closed"
    by_class = {e.user_class: e for e in profile.workload.user_mix}
    assert set(by_class) == {"ChatDbUser", "QueueUser"}
    assert by_class["ChatDbUser"].count == 1
    assert by_class["QueueUser"].count == 2
    users = profile.windows.measured_steps[0].users
    assert users == 3
    assert all((e.count or 0) > 0 for e in profile.workload.user_mix)
    assert profile.workload.axis_arrival_rates == {"queue": 1.0}


def test_compose_tutti_every_class_nonzero_population() -> None:
    profile = compose_axes_profile(list(STRESS_AXES))
    assert len(profile.workload.user_mix) >= len(STRESS_AXES)
    assert all((e.count or 0) > 0 for e in profile.workload.user_mix)
    expected = sum(solo_population(compose_axes_profile([axis])) for axis in STRESS_AXES)
    assert profile.windows.measured_steps[0].users == expected
    assert profile.workload.workload_model == "closed"


def test_suite_duet_expands_to_axes() -> None:
    assert resolve_suite_axes("chat_db_cpu_graph") == ["chat_db", "cpu_graph"]


def test_suite_tutti_is_all_axes() -> None:
    assert resolve_suite_axes("tutti") == list(STRESS_AXES)


def test_resolve_selection_axes_xor_suite() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        resolve_selection(axes=None, suite=None)
    with pytest.raises(ValueError, match="exactly one"):
        resolve_selection(axes="chat_db", suite="smoke")


def test_resolve_selection_rejects_external_apis_outside_natural() -> None:
    with pytest.raises(ValueError, match="external-apis"):
        resolve_selection(axes="chat_db", external_apis="live")
    with pytest.raises(ValueError, match="external-apis"):
        resolve_selection(suite="smoke", external_apis="live")


def test_resolve_selection_smoke_suite() -> None:
    profile, path, meta = resolve_selection(suite="smoke")
    assert profile.id == "all_protocols"
    assert path.exists()
    assert meta["selection"]["suite"] == "smoke"


def test_resolve_selection_natural_requires_external_apis() -> None:
    with pytest.raises(ValueError, match="external-apis"):
        resolve_selection(suite="natural")
    profile, _path, meta = resolve_selection(suite="natural", external_apis="stubbed")
    assert profile.external_apis == "stubbed"
    assert profile.movement_role == "natural"
    assert "natural" in profile.stress_categories
    assert meta["selection"]["external_apis"] == "stubbed"


def test_suites_catalog_has_expected_names() -> None:
    catalog = load_suites_catalog()
    assert set(catalog) >= {
        "chat_db_cpu_graph",
        "kb_ingest_kb_retrieve",
        "disk_io_ram_storage",
        "tutti",
        "smoke",
        "natural",
    }
