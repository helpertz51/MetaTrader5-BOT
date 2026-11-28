"""Reader for the versioned JSON snapshots exported by ICT_Library_MQ5.

Detection remains in the MQL5 library. This module validates the snapshot
envelope before the strategy layer is allowed to consume its records.
Only the Python standard library is required.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

STATUSES = {"READY", "PARTIAL", "NOT_READY", "ERROR", "DISABLED"}
DIRECTIONS = {"bullish", "bearish", "neutral"}
CONCEPTS = {
    "SWING_HIGH", "SWING_LOW", "BOS", "CHOCH", "ORDER_BLOCK", "FVG",
    "LIQUIDITY", "PREMIUM_DISCOUNT", "OTE", "KILL_ZONE", "BREAKER",
    "DISPLACEMENT", "MSS", "IFVG", "BPR", "PREVIOUS_DAY_HIGH",
    "PREVIOUS_DAY_LOW", "PREVIOUS_WEEK_HIGH", "PREVIOUS_WEEK_LOW",
    "SESSION_HIGH", "SESSION_LOW", "DAILY_GAP", "WEEKLY_GAP", "SMT", "PO3",
}
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\Z")


class SnapshotError(ValueError):
    """Raised when a snapshot is invalid or not safe to consume."""


@dataclass(frozen=True, slots=True)
class SmcRecord:
    id: str
    concept: str
    source_time: datetime
    confirmed_at: datetime
    updated_at: datetime
    direction: str
    lower: float
    upper: float
    state: str
    active: bool
    related_ids: tuple[str, ...]
    period_start: datetime | None
    period_end: datetime | None
    reference_price: float
    comparison_price: float
    strength: float
    reason: str


@dataclass(frozen=True, slots=True)
class SmcSnapshot:
    schema_version: str
    library_version: str
    symbol: str
    timeframe: str
    time_basis: str
    as_of: datetime | None
    status: str
    message: str
    modules: tuple[dict[str, Any], ...]
    records: tuple[SmcRecord, ...]
    raw: dict[str, Any]

    @property
    def is_tradeable(self) -> bool:
        """True only for a complete READY snapshot with a valid evaluation time."""
        return self.status == "READY" and self.as_of is not None


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotError(message)


def _timestamp(value: Any, field: str, *, nullable: bool = False) -> datetime | None:
    if nullable and value is None:
        return None
    _need(isinstance(value, str) and _TIMESTAMP.fullmatch(value) is not None,
          f"{field} must be broker time YYYY-MM-DDTHH:MM:SS")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise SnapshotError(f"{field} is not a valid date/time") from exc


def _finite(value: Any, field: str) -> float:
    _need(type(value) in (int, float), f"{field} must be numeric")
    number = float(value)
    _need(math.isfinite(number), f"{field} must be finite")
    return number


def _required(obj: Any, names: tuple[str, ...], field: str) -> dict[str, Any]:
    _need(isinstance(obj, dict), f"{field} must be an object")
    for name in names:
        _need(name in obj, f"{field}.{name} is required")
    return obj


def _record(item: Any, index: int) -> SmcRecord:
    path = f"records[{index}]"
    obj = _required(item, (
        "id", "concept", "source_time", "confirmed_at", "updated_at",
        "direction", "lower", "upper", "state", "active", "related_ids",
        "period_start", "period_end", "reference_price", "comparison_price",
        "strength", "reason",
    ), path)
    for name in ("id", "concept", "state", "reason"):
        _need(isinstance(obj[name], str), f"{path}.{name} must be a string")
    _need(bool(obj["id"]), f"{path}.id cannot be empty")
    _need(obj["concept"] in CONCEPTS, f"{path}.concept is unsupported")
    _need(obj["direction"] in DIRECTIONS, f"{path}.direction is unsupported")
    _need(type(obj["active"]) is bool, f"{path}.active must be boolean")
    _need(isinstance(obj["related_ids"], list)
          and all(isinstance(x, str) and x for x in obj["related_ids"]),
          f"{path}.related_ids must be an array of non-empty strings")
    lower = _finite(obj["lower"], f"{path}.lower")
    upper = _finite(obj["upper"], f"{path}.upper")
    _need(lower <= upper, f"{path}.lower cannot exceed upper")
    return SmcRecord(
        id=obj["id"], concept=obj["concept"],
        source_time=_timestamp(obj["source_time"], f"{path}.source_time"),
        confirmed_at=_timestamp(obj["confirmed_at"], f"{path}.confirmed_at"),
        updated_at=_timestamp(obj["updated_at"], f"{path}.updated_at"),
        direction=obj["direction"], lower=lower, upper=upper,
        state=obj["state"], active=obj["active"],
        related_ids=tuple(obj["related_ids"]),
        period_start=_timestamp(obj["period_start"], f"{path}.period_start", nullable=True),
        period_end=_timestamp(obj["period_end"], f"{path}.period_end", nullable=True),
        reference_price=_finite(obj["reference_price"], f"{path}.reference_price"),
        comparison_price=_finite(obj["comparison_price"], f"{path}.comparison_price"),
        strength=_finite(obj["strength"], f"{path}.strength"),
        reason=obj["reason"],
    )


def validate_snapshot(data: Any) -> SmcSnapshot:
    obj = _required(data, (
        "schema_version", "library_version", "symbol", "timeframe",
        "time_basis", "as_of", "status", "config", "modules", "records",
    ), "snapshot")
    for name in ("schema_version", "library_version", "symbol", "timeframe"):
        _need(isinstance(obj[name], str) and bool(obj[name]), f"{name} must be non-empty")
    _need(re.fullmatch(r"1\.\d+", obj["schema_version"]) is not None,
          "unsupported snapshot schema major version")
    _need(obj["time_basis"] == "broker", "snapshot time_basis must be broker")
    _need(obj["status"] in STATUSES, "snapshot status is unsupported")
    _need(isinstance(obj.get("message", ""), str), "snapshot message must be a string")
    as_of = _timestamp(obj["as_of"], "as_of", nullable=True)
    _need(isinstance(obj["config"], dict), "config must be an object")
    _need(isinstance(obj["modules"], list), "modules must be an array")
    _need(isinstance(obj["records"], list), "records must be an array")

    modules = []
    for i, module in enumerate(obj["modules"]):
        item = _required(module, ("concept", "status", "as_of", "truncated", "message"),
                         f"modules[{i}]")
        _need(item["concept"] in CONCEPTS, f"modules[{i}].concept is unsupported")
        _need(item["status"] in STATUSES, f"modules[{i}].status is unsupported")
        _timestamp(item["as_of"], f"modules[{i}].as_of", nullable=True)
        _need(type(item["truncated"]) is bool, f"modules[{i}].truncated must be boolean")
        _need(isinstance(item["message"], str), f"modules[{i}].message must be a string")
        modules.append(dict(item))

    records = tuple(_record(item, i) for i, item in enumerate(obj["records"]))
    ids = [record.id for record in records]
    _need(len(ids) == len(set(ids)), "record IDs must be unique")
    return SmcSnapshot(
        schema_version=obj["schema_version"], library_version=obj["library_version"],
        symbol=obj["symbol"], timeframe=obj["timeframe"], time_basis=obj["time_basis"],
        as_of=as_of, status=obj["status"], message=obj.get("message", ""),
        modules=tuple(modules), records=records, raw=dict(obj),
    )


def load_snapshot(path: str | Path) -> SmcSnapshot:
    """Load and validate one UTF-8 snapshot file."""
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            data = json.load(stream, parse_constant=lambda value: (_ for _ in ()).throw(
                SnapshotError(f"non-finite JSON value {value} is forbidden")))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"cannot read snapshot: {exc}") from exc
    return validate_snapshot(data)


def ready_records(snapshot: SmcSnapshot, *, concepts: set[str] | None = None) -> tuple[SmcRecord, ...]:
    """Return active records only when the whole snapshot is READY.

    Partial/stale/error snapshots are intentionally not forwarded to strategy.
    """
    if not snapshot.is_tradeable:
        return ()
    return tuple(
        record for record in snapshot.records
        if record.active and (concepts is None or record.concept in concepts)
    )
