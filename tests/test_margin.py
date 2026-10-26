import pytest

from shipcost.margin import margin


def test_margin_basic_math():
    m = margin(sell=60.00, item_cost=18.00, ship=9.42, packaging=0.50, fee_pct=13.25)
    assert m.fee_dollars == round(60.00 * 0.1325, 2)
    assert m.costs == 27.92
    assert m.profit == round(60.00 - 27.92 - 7.95, 2)
    assert m.margin_pct is not None and math_close(m.margin_pct, 24.13 / 60.00)
    assert m.roi_pct is not None and math_close(m.roi_pct, 24.13 / 27.92)


def math_close(a, b):
    return abs(a - b) < 1e-9


def test_margin_breakeven_includes_fee_percent():
    m = margin(sell=0, item_cost=18.00, ship=9.42, packaging=0.50, fee_pct=13.25)
    expected = 27.92 / (1 - 0.1325)
    assert m.breakeven_sell is not None
    assert math_close(m.breakeven_sell, expected)


def test_margin_breakeven_with_zero_fees():
    m = margin(sell=50, item_cost=10, ship=5, packaging=0, fee_pct=0)
    assert math_close(m.breakeven_sell, 15.0)


def test_margin_high_fee_no_breakeven():
    m = margin(sell=50, item_cost=10, ship=5, packaging=0, fee_pct=100)
    assert m.breakeven_sell is None


def test_margin_zero_sale_has_no_percentages():
    m = margin(sell=0, item_cost=18, ship=9, packaging=0, fee_pct=10)
    assert m.margin_pct is None
    assert m.roi_pct is not None


def test_margin_loss_is_negative_not_crash():
    m = margin(sell=10, item_cost=25, ship=9, packaging=1, fee_pct=13)
    assert m.profit < 0
    assert m.roi_pct < 0
