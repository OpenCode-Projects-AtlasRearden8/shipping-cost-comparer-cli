import pytest

from shipcost.models import Rate
from shipcost.store import RateStore, StoreError, parse_csv_text


def _rate(**overrides):
    base = dict(
        carrier="Sample Parcel Co.",
        service="Ground Value",
        zone="5",
        weight_lb=3.0,
        base_price=11.1,
        insurance_per_100=1.05,
        hand_min_days=3.0,
        hand_max_days=6.0,
    )
    base.update(overrides)
    return Rate(**base)


def test_parse_sample_rows():
    text = "\n".join(
        [
            "carrier,service,zone,weight_lb,base_price,insurance_per_100,hand_min_days,hand_max_days",
            "ACME Ground,saver,5,1,7.99,1.05,2,4",
            "ACME Ground,saver,5,3,10.49,1.05,3,6",
        ]
    )
    rates, warnings = parse_csv_text(text)
    assert warnings == []
    assert len(rates) == 2
    assert rates[1].base_price == 10.49
    assert rates[1].hand_max_days == 6.0


def test_parse_money_symbols_and_quotes():
    text = "carrier,service,zone,weight_lb,base_price\nACME,saver,5,2,\"$1,234.50\"\n"
    rates, warnings = parse_csv_text(text)
    assert rates[0].base_price == 1234.50


def test_parse_row_longer_than_header_is_skipped():
    text = "carrier,service,zone,weight_lb,base_price\nACME,saver,5,2,$1,234.50\n"
    rates, warnings = parse_csv_text(text)
    assert rates == []
    assert any("extra value" in w for w in warnings)


def test_parse_missing_optional_columns_get_defaults():
    text = "carrier,service,zone,weight_lb,base_price\nACME,saver,5,2,12.50\n"
    rates, warnings = parse_csv_text(text)
    assert warnings == []
    assert rates[0].insurance_per_100 == 0.0
    assert rates[0].hand_min_days is None
    assert rates[0].hand_max_days is None


def test_parse_missing_required_column_raises():
    with pytest.raises(ValueError) as exc:
        parse_csv_text("carrier,service,zone,weight_lb\nACME,saver,5,1\n")
    assert "base_price" in str(exc.value)


def test_parse_bad_row_is_skipped_with_warning():
    text = "\n".join(
        [
            "carrier,service,zone,weight_lb,base_price",
            "ACME,saver,5,1,7.99",
            "ACME,saver,5,notanumber,7.99",
            "ACME,saver,5,2,8.99",
        ]
    )
    rates, warnings = parse_csv_text(text)
    assert len(rates) == 2
    assert any("not a number" in w for w in warnings)


def test_parse_default_carrier_for_rows_without_carrier_column():
    text = "service,zone,weight_lb,base_price\nsaver,5,1,7.99\n"
    rates, warnings = parse_csv_text(text, default_carrier="Pasted Co")
    assert len(rates) == 1
    assert rates[0].carrier == "Pasted Co"


def test_add_dedupes_identical_rows(tmp_path):
    store = RateStore(tmp_path)
    added, skipped = store.add([_rate(), _rate(zone="1")])
    assert (added, skipped) == (2, 0)
    added, skipped = store.add([_rate(), _rate(zone="1")])
    assert (added, skipped) == (0, 2)
    assert len(store.load()) == 2


def test_add_replace_wipes_existing(tmp_path):
    store = RateStore(tmp_path)
    store.add([_rate(), _rate(zone="1")])
    added, _ = store.add([_rate(zone="8")], replace=True)
    assert added == 1
    remaining = store.load()
    assert len(remaining) == 1
    assert remaining[0].zone == "8"


def test_roundtrip_preserves_fields(tmp_path):
    store = RateStore(tmp_path)
    r = _rate(carrier="Flash Courier", service="Night Jet", zone="z-9", weight_lb=12.5, base_price=24.75, hand_min_days=1.0, hand_max_days=2.0)
    store.add([r])
    assert store.load() == [r]


def test_load_raises_storeerror_on_corrupt_file(tmp_path):
    store = RateStore(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    store.rates_path.write_text("carrier,service,zone,weight_lb,base_price\nOOPS\n")
    with pytest.raises(StoreError):
        store.load()


def test_clear_removes_file(tmp_path):
    store = RateStore(tmp_path)
    store.add([_rate()])
    assert store.clear() is True
    assert store.clear() is False
    assert not store.rates_path.exists()


def test_sample_tables_parse_unique(tmp_path, sample_csv_path):
    text = sample_csv_path.read_text(encoding="utf-8")
    rates, warnings = parse_csv_text(text)
    assert warnings == []
    assert len(rates) == 60
    assert len({r.dedupe_key for r in rates}) == 60
    carriers = {r.carrier for r in rates}
    assert carriers == {"Sample Parcel Co.", "Sample Express Inc."}
    zones = {r.zone for r in rates}
    assert zones == {"Local", "1", "2", "3", "5", "8"}
