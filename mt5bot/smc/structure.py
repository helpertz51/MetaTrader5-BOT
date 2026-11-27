
"""Confirmed swing-point and market-structure detection.

The detector uses closed OHLC candles only. A swing is confirmed after
the configured number of candles to its right have closed. Breaks are
confirmed by candle close, never by wick alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


Direction = Literal["bullish", "bearish"]
SwingKind = Literal["high", "low"]
EventKind = Literal["BOS", "CHOCH"]


class StructureDataError(ValueError):
    """Raised when OHLC input is invalid."""


@dataclass(frozen=True, slots=True)
class SwingPoint:
    index: int
    time: object
    price: float
    kind: SwingKind


@dataclass(frozen=True, slots=True)
class StructureEvent:
    index: int
    time: object
    event: EventKind
    direction: Direction
    level: float
    swing_index: int


@dataclass(frozen=True, slots=True)
class StructureResult:
    bias: Direction | None
    swings: tuple[SwingPoint, ...]
    events: tuple[StructureEvent, ...]


def _validate_bars(bars: pd.DataFrame) -> None:
    required = {"high", "low", "close"}

    if not isinstance(bars, pd.DataFrame):
        raise StructureDataError("bars must be a pandas DataFrame")

    missing = required.difference(bars.columns)
    if missing:
        raise StructureDataError(
            f"Missing required OHLC columns: {sorted(missing)}"
        )

    if bars.empty:
        raise StructureDataError("bars cannot be empty")

    for column in required:
        values = pd.to_numeric(bars[column], errors="coerce")
        if values.isna().any():
            raise StructureDataError(
                f"Column '{column}' contains invalid or missing values"
            )

        if not values.map(lambda value: float("-inf") < value < float("inf")).all():
            raise StructureDataError(
                f"Column '{column}' contains non-finite values"
            )

    if (bars["high"] < bars["low"]).any():
        raise StructureDataError("A candle high cannot be below its low")

    if ((bars["close"] > bars["high"]) |
            (bars["close"] < bars["low"])).any():
        raise StructureDataError(
            "Every candle close must be between its high and low"
        )


def detect_market_structure(
    bars: pd.DataFrame,
    *,
    left_bars: int = 2,
    right_bars: int = 2,
) -> StructureResult:
    """Detect confirmed swing points and close-confirmed BOS/CHOCH events.

    Args:
        bars: DataFrame containing high, low and close columns.
              An optional time column is used for event timestamps.
        left_bars: Candles required on the left of a swing.
        right_bars: Candles required on the right to confirm a swing.

    Returns:
        Immutable result containing the latest structural bias,
        confirmed swing points and chronological structure events.

    Notes:
        - A swing is not available until its right-side candles close.
        - A wick crossing a swing level does not count as a break.
        - The first confirmed break is classified as BOS.
        - A break against the previous structural direction is CHOCH.
        - If one candle closes beyond both active swing levels,
          that candle is treated as ambiguous and generates no event.
    """
    _validate_bars(bars)

    if (
        isinstance(left_bars, bool)
        or isinstance(right_bars, bool)
        or not isinstance(left_bars, int)
        or not isinstance(right_bars, int)
        or left_bars < 1
        or right_bars < 1
    ):
        raise ValueError("left_bars and right_bars must be positive integers")

    highs = bars["high"].astype(float).tolist()
    lows = bars["low"].astype(float).tolist()
    closes = bars["close"].astype(float).tolist()

    if "time" in bars.columns:
        times = bars["time"].tolist()
    else:
        times = bars.index.tolist()

    swings: list[SwingPoint] = []
    events: list[StructureEvent] = []

    active_high: SwingPoint | None = None
    active_low: SwingPoint | None = None
    broken_high_index: int | None = None
    broken_low_index: int | None = None
    bias: Direction | None = None

    first_confirmation_index = left_bars + right_bars

    for current_index in range(first_confirmation_index, len(bars)):
        pivot_index = current_index - right_bars

        left_start = pivot_index - left_bars
        right_end = pivot_index + right_bars + 1

        pivot_high = highs[pivot_index]
        pivot_low = lows[pivot_index]

        surrounding_highs = (
            highs[left_start:pivot_index]
            + highs[pivot_index + 1:right_end]
        )
        surrounding_lows = (
            lows[left_start:pivot_index]
            + lows[pivot_index + 1:right_end]
        )

        is_swing_high = all(
            pivot_high > value for value in surrounding_highs
        )
        is_swing_low = all(
            pivot_low < value for value in surrounding_lows
        )

        # A single outside candle cannot be both a confirmed high and low.
        if is_swing_high and not is_swing_low:
            point = SwingPoint(
                index=pivot_index,
                time=times[pivot_index],
                price=pivot_high,
                kind="high",
            )
            swings.append(point)
            active_high = point
            broken_high_index = None

        elif is_swing_low and not is_swing_high:
            point = SwingPoint(
                index=pivot_index,
                time=times[pivot_index],
                price=pivot_low,
                kind="low",
            )
            swings.append(point)
            active_low = point
            broken_low_index = None

        close = closes[current_index]

        bullish_break = (
            active_high is not None
            and broken_high_index != active_high.index
            and close > active_high.price
        )
        bearish_break = (
            active_low is not None
            and broken_low_index != active_low.index
            and close < active_low.price
        )

        if bullish_break and bearish_break:
            continue

        if bullish_break:
            event: EventKind = (
                "BOS" if bias in (None, "bullish") else "CHOCH"
            )
            events.append(
                StructureEvent(
                    index=current_index,
                    time=times[current_index],
                    event=event,
                    direction="bullish",
                    level=active_high.price,
                    swing_index=active_high.index,
                )
            )
            broken_high_index = active_high.index
            bias = "bullish"

        elif bearish_break:
            event = "BOS" if bias in (None, "bearish") else "CHOCH"
            events.append(
                StructureEvent(
                    index=current_index,
                    time=times[current_index],
                    event=event,
                    direction="bearish",
                    level=active_low.price,
                    swing_index=active_low.index,
                )
            )
            broken_low_index = active_low.index
            bias = "bearish"

    return StructureResult(
        bias=bias,
        swings=tuple(swings),
        events=tuple(events),
    )
