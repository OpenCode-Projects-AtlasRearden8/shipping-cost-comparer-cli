import pytest

from shipcost import __version__
from shipcost.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "shipcost" in out and __version__ in out


def test_demo_installs_rates(demo, run_cli):
    assert demo.exists()
    code, out, err = run_cli("rates")
    assert code == 0
    assert "Sample Parcel Co." in out
    assert "60 of 60" in out


def test_import_file_then_dedupe(run_cli, sample_csv_path, data_dir):
    code, out, err = run_cli("import", "--file", str(sample_csv_path))
    assert code == 0
    assert "added   60" in out
    assert data_dir.joinpath("rates.csv").exists()
    code, out, err = run_cli("import", "--file", str(sample_csv_path))
    assert code == 0
    assert "added   0" in out
    assert "skipped 60" in out


def test_import_paste_with_carrier_override(run_cli, data_dir):
    pasted = "service,zone,weight_lb,base_price\nmini,2,1,6.25\n"
    code, out, err = run_cli("import", "--paste", "--carrier", "Kwik Feet", stdin=pasted)
    assert code == 0
    assert "added   1" in out
    code, out, err = run_cli("rates", "--carrier", "Kwik Feet")
    assert code == 0
    assert "Kwik Feet" in out and "mini" in out


def test_import_bad_header_is_friendly_error(run_cli, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("oops,what,columns\n1,2,3\n", encoding="utf-8")
    code, out, err = run_cli("import", "--file", str(bad))
    assert code == 2
    assert "base_price" in err
    assert err.strip().startswith("error:")


def test_import_empty_table_is_friendly_error(run_cli, tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("carrier,service,zone,weight_lb,base_price\n", encoding="utf-8")
    code, out, err = run_cli("import", "--file", str(empty))
    assert code == 2
    assert "nothing importable" in err


def test_import_missing_file_is_friendly_error(run_cli):
    code, out, err = run_cli("import", "--file", "/nonexistent/path/rates.csv")
    assert code == 2
    assert err.strip().startswith("error:")
    assert "Traceback" not in err


def test_compare_shows_insurance_and_handling(demo, run_cli):
    code, out, err = run_cli("compare", "--weight", "2", "--zone", "5", "--value", "45")
    assert code == 0
    assert "Handling" in out
    assert "Ins" in out
    assert "$11.05" in out
    assert "$20.65" in out


def test_compare_dims_card_and_margin(demo, run_cli):
    argv = (
        "compare",
        "--weight", "2",
        "--dims", "12x9x4",
        "--zone", "5",
        "--value", "45",
        "--sell", "46",
        "--item-cost", "12",
        "--fee-pct", "13.25",
        "--card",
    )
    code, out, err = run_cli(*argv)
    assert code == 0
    assert "3.11" in out
    assert "$13.25" in out
    assert "$24.35" in out
    assert "Profit" in out
    assert "CHEAT CARD" in out
    assert "nothing was scraped" in out


def test_compare_without_rates_hints_demo(run_cli, data_dir):
    code, out, err = run_cli("compare", "--weight", "1", "--zone", "5")
    assert code == 1
    assert "demo" in err


def test_compare_negative_weight_is_friendly_error(demo, run_cli):
    code, out, err = run_cli("compare", "--weight", "-2", "--zone", "5")
    assert code == 2
    assert "negative" in err


def test_compare_unknown_zone_mentions_zone(demo, run_cli):
    code, out, err = run_cli("compare", "--weight", "1", "--zone", "77")
    assert code == 1
    assert "zone '77'" in err


def test_compare_bad_dims_is_friendly_error(demo, run_cli):
    code, out, err = run_cli("compare", "--weight", "1", "--dims", "9x9", "--zone", "5")
    assert code == 2
    assert "dims" in err


def test_margin_end_to_end(run_cli):
    code, out, err = run_cli(
        "margin", "--sell", "60", "--ship", "9.42", "--item-cost", "18", "--packaging", "0.5", "--fee-pct", "13.25"
    )
    assert code == 0
    assert "$7.95" in out
    assert "$24.13" in out
    assert "86.4%" in out
    assert "$32.18" in out


def test_margin_rejects_bad_fee(run_cli):
    code, out, err = run_cli("margin", "--sell", "60", "--fee-pct", "150")
    assert code == 2
    assert "--fee-pct" in err


def test_blank_card(run_cli):
    code, out, err = run_cli("card")
    assert code == 0
    assert "CHEAT CARD" in out
    assert "item cost: $______" in out


def test_zone_listing(demo, run_cli):
    code, out, err = run_cli("zones")
    assert code == 0
    assert "Local" in out
    assert "5  (10 row(s))" in out


def test_where_shows_paths(run_cli, data_dir):
    code, out, err = run_cli("where")
    assert code == 0
    assert str(data_dir) in out
    assert "No network" in out


def test_clear_with_confirm_no_and_yes(demo, run_cli):
    code, out, err = run_cli("clear", stdin="n\n")
    assert code == 0
    assert "Cancelled" in out
    assert demo.exists()
    code, out, err = run_cli("clear", "--yes")
    assert code == 0
    assert "deleted" in out
    assert not demo.exists()


def test_rates_filter_no_match(demo, run_cli):
    code, out, err = run_cli("rates", "--zone", "77")
    assert code == 0
    assert "No rows match" in out
