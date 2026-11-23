"""JSON/Data string output preserves datetime instants and legacy formatting."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from lfx.schema.data import JSON, Data, custom_serializer, serialize_data


class UndefinedOffset(tzinfo):
    def utcoffset(self, _value):
        return None

    def dst(self, _value):
        return None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=2))), "2025-12-31 22:30:00 UTC"),
        (datetime(2026, 12, 31, 23, 30, tzinfo=timezone(timedelta(hours=-2))), "2027-01-01 01:30:00 UTC"),
        (datetime(2024, 3, 1, 0, 15, tzinfo=timezone(timedelta(hours=5, minutes=45))), "2024-02-29 18:30:00 UTC"),
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=-3, minutes=-30))), "2026-01-01 03:30:00 UTC"),
        (datetime(2026, 1, 1, 1, 2, 3, 999999, tzinfo=timezone.utc), "2026-01-01 01:02:03 UTC"),
        (datetime(2026, 1, 1, 1, 2, 3, 999999), "2026-01-01 01:02:03 UTC"),  # noqa: DTZ001
        (datetime(2026, 1, 1, 1, 2, 3, tzinfo=UndefinedOffset()), "2026-01-01 01:02:03 UTC"),
        (datetime(1000, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))), "1000-01-01 00:00:00 UTC"),
        (datetime(9999, 12, 31, 22, tzinfo=timezone(timedelta(hours=-1))), "9999-12-31 23:00:00 UTC"),
    ],
)
def test_datetime_helper_and_public_nested_json(value, expected):
    identity = (value.isoformat(), value.tzinfo, value.fold)
    assert json.loads(serialize_data({"date": value}))["date"] == expected
    assert json.loads(serialize_data({"date": value})) == {"date": expected}
    assert Data is JSON
    record = Data(data={"nested": [{"date": value}], "normal": 42})
    assert json.loads(str(record)) == {"nested": [{"date": expected}], "normal": 42}
    assert record.data["nested"][0]["date"] is value
    assert (value.isoformat(), value.tzinfo, value.fold) == identity


@pytest.mark.parametrize(("fold", "expected"), [(0, "2026-11-01 05:30:00 UTC"), (1, "2026-11-01 06:30:00 UTC")])
def test_daylight_saving_fold_keeps_distinct_instants(fold, expected):
    # No skip: unavailable timezone data is a test failure, not silent coverage loss.
    value = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=fold)
    assert json.loads(str(Data(data={"date": value})))["date"] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime.min.replace(tzinfo=timezone(timedelta(hours=1))), "0001-01-01T00:00:00+01:00"),
        (datetime.max.replace(tzinfo=timezone(timedelta(hours=-1))), "9999-12-31T23:59:59.999999-01:00"),
    ],
)
def test_utc_overflow_retains_original_offset_in_valid_json(value, expected):
    result = json.loads(str(Data(data={"nested": [{"date": value}], "normal": "kept"})))
    assert result == {"nested": [{"date": expected}], "normal": "kept"}
    assert json.loads(serialize_data({"date": value}))["date"] == expected
    # The original offset and local fields encode the same instant without an
    # unrepresentable UTC conversion. No clamping or mislabeled UTC timestamp.
    assert datetime.fromisoformat(expected) == value


def test_naive_datetime_does_not_use_host_timezone():
    script = """
import json, time
from datetime import datetime
from lfx.schema.data import Data
assert hasattr(time, 'tzset')
time.tzset()
assert time.timezone != 0
value = datetime(2026, 1, 2, 3, 4, 5)
assert json.loads(str(Data(data={'date': value}))) == {'date': '2026-01-02 03:04:05 UTC'}
"""
    result = subprocess.run(  # noqa: S603 - fixed interpreter and literal offline script
        [sys.executable, "-c", script],
        env={**os.environ, "TZ": "EST5EDT"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_non_datetime_custom_serialization_unchanged():
    value = {"number": Decimal("1.25"), "id": UUID(int=1), "bytes": b"hello", "none": None, "false": False}
    assert json.loads(serialize_data(value)) == {
        "number": 1.25,
        "id": "00000000-0000-0000-0000-000000000001",
        "bytes": "hello",
        "none": None,
        "false": False,
    }
    with pytest.raises(TypeError, match="not serializable"):
        custom_serializer(object())


def test_public_serializer_keeps_persisted_document_id_bytes():
    from uuid import NAMESPACE_X500, uuid5

    value = datetime(2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=2)))
    metadata = {"when": value}
    encoded = json.dumps(metadata, sort_keys=True, default=custom_serializer)
    assert encoded == '{"when": "2026-01-01 00:30:00 UTC"}'
    assert str(uuid5(NAMESPACE_X500, "payload" + encoded)) == "c4147933-12f3-52c4-b38f-4b76c4865e82"
    assert json.loads(str(Data(data=metadata))) == {"when": "2025-12-31 22:30:00 UTC"}


def test_nested_model_datetimes_use_private_json_default():
    from pydantic import BaseModel

    class Payload(BaseModel):
        date: datetime

    value = datetime(2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=2)))
    assert json.loads(serialize_data({"model": Payload(date=value)})) == {"model": {"date": "2025-12-31 22:30:00 UTC"}}


def test_non_overflow_conversion_errors_propagate_and_public_string_falls_back(monkeypatch):
    from lfx.schema import data as module

    failure = ValueError("sentinel conversion error")

    def fail(_value):
        raise failure

    monkeypatch.setattr(module, "ensure_utc", fail)
    value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="sentinel conversion error") as caught:
        serialize_data({"date": value})
    assert caught.value is failure
    record = Data(data={"date": value})
    assert str(record) == str(record.data)


def test_unsupported_date_and_datetime_keys_keep_existing_errors_and_repr_fallback():
    from datetime import date

    value = date(2026, 1, 1)
    with pytest.raises(TypeError, match=r"Type <class 'datetime.date'> not serializable"):
        serialize_data({"date": value})
    record = Data(data={"date": value})
    assert str(record) == str(record.data)
    key = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(TypeError, match="keys must be str, int, float, bool or None, not datetime"):
        serialize_data({key: "value"})
    record = Data(data={key: "value"})
    assert str(record) == str(record.data)
