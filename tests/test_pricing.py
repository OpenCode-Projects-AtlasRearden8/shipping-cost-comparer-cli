import math

import pytest

from shipcost.models import Rate, Shipment
from shipcost.pricing import billed_weight, insurance_fee, options_for, parse_dims


def test_parse_dims_basic():
    assert parse_dims("12x9x4") == (12.0, 9.0, 4.0)
    assert parse_dims("12X9X4") == (12.0, 9.0, 4.0)


def test_parse_dims_rejects_bad_input():
    with pytest.raises(ValueError):
        parse_dims("12x9")
    with pytest.raises(ValueError):
        parse_dims("a x b x c")
    with pytest.raises(ValueError):
        parse_dims("0x9x4")


def test_billed_weight_uses_max_of_actual_and_dim():
    assert billed_weight(2.0, None, 139) == 2.0
    assert math.isclose(billed_weight(2.0, (12.0, 9.0, 4.0), 139), 3.11)
    assert math.isclose(billed_weight(5.0, (6.0, 4.0, 2.0), 139), 5.0)
    assert math.isclose(billed_weight(2.0, (12.0, 9.0, 4.0), 166), 2.61)


def test_billed_weight_rejects_bad_divisor():
    with pytest.raises(ValueError):
        billed_weight(2.0, (12.0, 9.0, 4.0), 0)


def test_insurance_fee_rounds_up_per_100():
    rate = Rate("ACME", "saver", "5", 1.0, 7.99, insurance_per_100=1.05)
    assert insurance_fee(rate, 0) == 0.0
    assert insurance_fee(rate, 45) == 1.05
    assert insurance_fee(rate, 100) == 1.05
    assert insurance_fee(rate, 100.01) == 2.10
    assert insurance_fee(rate, 150) == 2.10
    free_ins = Rate("ACME", "saver", "5", 1.0, 7.99, insurance_per_100=0.0)
    assert insurance_fee(free_ins, 400) == 0.0


def test_options_filter_by_zone():
    rates = [
        Rate("ACME", "saver", "5", 3.0, 11.10, 1.05, 3, 6),
        Rate("ACME", "saver", "1", 3.0, 9.90, 1.05, 2, 4),
    ]
    shipment = Shipment(weight_lb=2.0, dims=None, divisor=139, zone="5", declared_value=0, extras=0)
    opts = options_for(rates, shipment)
    assert len(opts) == 1
    assert opts[0].rate.zone == "5"


def test_options_pick_smallest_covering_break():
    rates = [
        Rate("ACME", "saver", "5", 3.0, 11.10),
        Rate("ACME", "saver", "5", 5.0, 13.10),
        Rate("ACME", "saver", "5", 10.0, 17.60),
    ]
    shipment = Shipment(weight_lb=2.6, dims=None, divisor=139, zone="5", declared_value=0, extras=0)
    opts = options_for(rates, shipment)
    assert opts[0].rate.weight_lb == 3.0


def test_options_rank_by_landed_then_speed():
    rates = [
        Rate("Slow Coach", "ground", "5", 3.0, 10.00, 1.00, 4, 7),
        Rate("Flash", "air", "5", 3.0, 10.00, 1.00, 1, 2),
        Rate("Flash", "ground", "5", 3.0, 12.00, 1.00, 2, 3),
    ]
    shipment = Shipment(weight_lb=1.5, dims=None, divisor=139, zone="5", declared_value=100, extras=0)
    opts = options_for(rates, shipment)
    assert [o.rate.service for o in opts] == ["air", "ground", "ground"]
    assert opts[0].rate.carrier == "Flash"
    assert opts[1].rate.carrier == "Slow Coach"


def test_options_dedupe_carrier_service_keeps_cheapest():
    rates = [
        Rate("Flash", "air", "5", 3.0, 12.00, 1.00, 1, 2),
        Rate("Flash", "air", "5", 5.0, 11.00, 1.00, 1, 2),
    ]
    shipment = Shipment(weight_lb=1.0, dims=None, divisor=139, zone="5", declared_value=0, extras=0)
    opts = options_for(rates, shipment)
    assert len(opts) == 1
    assert opts[0].rate.weight_lb == 5.0
    assert opts[0].landed == 11.00


def test_options_landed_includes_insurance_and_extras():
    rates = [Rate("ACME", "saver", "5", 3.0, 11.10, 1.05, 3, 6)]
    shipment = Shipment(weight_lb=2.0, dims=None, divisor=139, zone="5", declared_value=45, extras=0.75)
    opts = options_for(rates, shipment)
    assert opts[0].insurance == 1.05
    assert opts[0].landed == round(11.10 + 1.05 + 0.75, 2)


def test_options_empty_when_nothing_covers_weight():
    rates = [Rate("ACME", "saver", "5", 2.0, 8.00)]
    shipment = Shipment(weight_lb=9.9, dims=None, divisor=139, zone="5", declared_value=0, extras=0)
    assert options_for(rates, shipment) == []


def test_options_empty_on_zone_mismatch():
    rates = [Rate("ACME", "saver", "5", 3.0, 11.10)]
    shipment = Shipment(weight_lb=1.0, dims=None, divisor=139, zone="7", declared_value=0, extras=0)
    assert options_for(rates, shipment) == []
