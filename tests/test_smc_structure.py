"""Tests for the SMC market-structure detector."""

import pandas as pd
import pytest

from mt5bot.smc.structure import StructureDataError, detect_market_structure


def make_bars(high, low, close):
    return pd.DataFrame(
        {
            "high": high,
            "low": low,
            "close": close,
        }
    )


def test_detects_confirmed_swing_high():
    bars = make_bars(
        high=[7, 8, 10, 8, 9],
        low=[5, 6, 7, 6, 7],
        close=[6, 7, 9, 7, 8],
    )

    result = detect_market_structure(bars)

    swing_highs = [
        swing for swing in result.swings if swing.kind == "high"
    ]

    assert len(swing_highs) == 1
    assert swing_highs[0].index == 2
    assert swing_highs[0].price == 10


def test_detects_bullish_bos_after_close_above_swing():
    bars = make_bars(
        high=[7, 8, 10, 8, 9, 12],
        low=[5, 6, 7, 6, 7, 8],
        close=[6, 7, 9, 7, 8, 11],
    )

    result = detect_market_structure(bars)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event == "BOS"
    assert event.direction == "bullish"
    assert event.index == 5
    assert event.level == 10
    assert result.bias == "bullish"


def test_wick_break_without_close_does_not_create_bos():
    bars = make_bars(
        high=[7, 8, 10, 8, 9, 12],
        low=[5, 6, 7, 6, 7, 8],
        close=[6, 7, 9, 7, 8, 9],
    )

    result = detect_market_structure(bars)

    assert result.events == ()
    assert result.bias is None


def test_detects_choch_after_opposite_structural_break():
    bars = make_bars(
        high=[5, 10, 7, 8, 9, 11, 9],
        low=[2, 4, 5, 2, 4, 5, 0.5],
        close=[4, 8, 6, 7, 6, 11, 1],
    )

    result = detect_market_structure(
        bars,
        left_bars=1,
        right_bars=1,
    )

    assert len(result.events) == 2
    first, second = result.events

    assert first.event == "BOS"
    assert first.direction == "bullish"
    assert first.index == 5
    assert second.event == "CHOCH"
    assert second.direction == "bearish"
    assert second.index == 6
    assert result.bias == "bearish"


def test_swing_is_not_confirmed_before_right_bars_close():
    bars = make_bars(
        high=[7, 8, 10, 8, 9],
        low=[5, 6, 7, 6, 7],
        close=[6, 7, 9, 7, 8],
    )

    before_confirmation = detect_market_structure(bars.iloc[:4])
    after_confirmation = detect_market_structure(bars)

    assert before_confirmation.swings == ()
    assert any(
        swing.index == 2
        for swing in after_confirmation.swings
    )


def test_rejects_missing_ohlc_columns():
    bars = pd.DataFrame(
        {
            "high": [10, 11],
            "close": [9, 10],
        }
    )

    with pytest.raises(StructureDataError):
        detect_market_structure(bars)


def test_rejects_nan_values():
    bars = make_bars(
        high=[10, float("nan"), 12],
        low=[5, 6, 7],
        close=[8, 9, 10],
    )

    with pytest.raises(StructureDataError):
        detect_market_structure(bars)


def test_rejects_high_below_low():
    bars = make_bars(
        high=[5, 4, 6],
        low=[6, 3, 4],
        close=[5, 3.5, 5],
    )

    with pytest.raises(StructureDataError):
        detect_market_structure(bars)


def test_rejects_close_outside_candle_range():
    bars = make_bars(
        high=[10, 11, 12],
        low=[5, 6, 7],
        close=[8, 12, 10],
    )

    with pytest.raises(StructureDataError):
        detect_market_structure(bars)


@pytest.mark.parametrize(
    ("left_bars", "right_bars"),
    [
        (0, 2),
        (2, 0),
        (-1, 2),
        (2, -1),
    ],
)
def test_rejects_invalid_swing_parameters(left_bars, right_bars):
    bars = make_bars(
        high=[5, 8, 6],
        low=[2, 3, 4],
        close=[4, 6, 5],
    )

    with pytest.raises(ValueError):
        detect_market_structure(
            bars,
            left_bars=left_bars,
            right_bars=right_bars,
        )
