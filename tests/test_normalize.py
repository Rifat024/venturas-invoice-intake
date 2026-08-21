from invoice_intake.normalize import (
    normalize_unit, tax_rate_to_code, to_iso_date,
)


def test_iso_and_slash_dates():
    assert to_iso_date("2026-02-05") == "2026-02-05"
    assert to_iso_date("2026/01/18") == "2026-01-18"
    assert to_iso_date("2026/3/31") == "2026-03-31"


def test_japanese_year_dates():
    assert to_iso_date("2026年1月7日") == "2026-01-07"
    assert to_iso_date("2026年2月10日") == "2026-02-10"


def test_reiwa_era_dates():
    # 令和 base is 2018; 令和8年 == 2026 (invoice_11).
    assert to_iso_date("令和8年2月5日") == "2026-02-05"
    assert to_iso_date("令和8年3月31日") == "2026-03-31"
    assert to_iso_date("令和元年5月1日") == "2019-05-01"


def test_unparseable_date_returns_none():
    assert to_iso_date("Feb 5, 2026") is None
    assert to_iso_date("2026-13-40") is None
    assert to_iso_date("") is None


def test_tax_rate_to_code():
    assert tax_rate_to_code(10) == "T10"
    assert tax_rate_to_code(8) == "T08"
    assert tax_rate_to_code(5) is None


def test_unit_defaults_to_lump_sum():
    assert normalize_unit("") == "式"
    assert normalize_unit(None) == "式"
    assert normalize_unit("箱") == "箱"
