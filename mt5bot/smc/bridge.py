"""Read-only bridge for snapshots exported to MT5 Common/Files."""
from __future__ import annotations

import os
from pathlib import Path

from .snapshot import SmcSnapshot, SnapshotError, load_snapshot


def common_files_dir() -> Path:
    configured = os.environ.get("MT5_COMMON_FILES")
    if not configured:
        raise SnapshotError(
            "MT5_COMMON_FILES is not set. Point it to the MT5 Common/Files directory."
        )
    directory = Path(configured).expanduser()
    if not directory.is_dir():
        raise SnapshotError(
            f"MT5_COMMON_FILES directory does not exist: {directory}"
        )
    return directory


def read_latest_snapshot(
    filename: str = "smc_snapshot.json",
    require_ready: bool = True,
) -> SmcSnapshot:
    if Path(filename).name != filename or filename in {"", ".", ".."}:
        raise SnapshotError("filename must be a simple file name")

    snapshot = load_snapshot(common_files_dir() / filename)

    if require_ready and not snapshot.is_tradeable:
        raise SnapshotError(
            f"Snapshot is not tradeable: status={snapshot.status}"
        )

    return snapshot
