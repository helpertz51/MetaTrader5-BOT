
"""Smart Money Concepts (SMC) analysis package."""

from mt5bot.smc.structure import (
    Direction,
    EventKind,
    StructureDataError,
    StructureEvent,
    StructureResult,
    SwingKind,
    SwingPoint,
    detect_market_structure,
)

__all__ = [
    "Direction",
    "EventKind",
    "StructureDataError",
    "StructureEvent",
    "StructureResult",
    "SwingKind",
    "SwingPoint",
    "detect_market_structure",
]
