"""Pure tests for the fiscal engine - no AWS, no mocks."""

from decimal import Decimal

from common.fiscal import compare_amounts, run_fiscal_check


def _goods(taxes, **overrides):
    goods = {"valoare_statistica": Decimal("10000"),
             "masa_neta_kg": Decimal("50"), "taxe": taxes}
    goods.update(overrides)
    return goods


def test_ad_valorem_duty_and_vat_on_compound_base():
    entry = {"duty_rate": Decimal("10"), "vat_rate": Decimal("20")}
    goods = _goods([
        {"tip": "Taxa vamală", "suma": 1000},
        {"tip": "TVA", "suma": 2200},  # (10000 + 1000) * 20%
    ])
    result = run_fiscal_check(goods, entry)
    assert result["status"] == "PASS"
    assert result["components"]["duty"]["expected"] == Decimal("1000.00")
    assert result["components"]["vat"]["expected"] == Decimal("2200.00")


def test_excise_per_kg_enters_the_vat_base():
    entry = {"duty_rate": Decimal("15"), "vat_rate": Decimal("20"),
             "excise": {"amount": Decimal("120"), "per": "kg"}}
    goods = _goods([
        {"tip": "Taxa vamală", "suma": 1500},
        {"tip": "Acciz", "suma": 6000},          # 120 x 50 kg
        {"tip": "TVA", "suma": 3500},            # (10000+1500+6000) * 20%
    ])
    result = run_fiscal_check(goods, entry)
    assert result["components"]["excise"]["expected"] == Decimal("6000.00")
    assert result["components"]["vat"]["expected"] == Decimal("3500.00")
    assert result["status"] == "PASS"


def test_undeclared_tax_counts_as_zero_and_fails():
    entry = {"duty_rate": Decimal("10"), "vat_rate": Decimal("20")}
    goods = _goods([{"tip": "TVA", "suma": 2200}])  # duty row missing
    result = run_fiscal_check(goods, entry)
    assert result["components"]["duty"] == {
        "status": "MISMATCH", "expected": Decimal("1000.00"),
        "declared": Decimal("0.00")}
    assert result["status"] == "FAIL"


def test_tolerance_is_max_of_one_unit_and_half_percent():
    # expected 1000 -> tolerance max(1, 5) = 5
    assert compare_amounts(Decimal("1000"), Decimal("1004"))["status"] == "MATCH"
    assert compare_amounts(Decimal("1000"), Decimal("1006"))["status"] == "MISMATCH"
    # expected 40 -> tolerance max(1, 0.2) = 1
    assert compare_amounts(Decimal("40"), Decimal("40.9"))["status"] == "MATCH"
    assert compare_amounts(Decimal("40"), Decimal("41.5"))["status"] == "MISMATCH"


def test_procedure_fee_row_is_not_mistaken_for_duty():
    """"Taxa pentru proceduri vamale" contains "vam" but is NOT the duty."""
    entry = {"duty_rate": Decimal("10"), "vat_rate": Decimal("20")}
    goods = _goods([
        {"tip": "Taxa pentru proceduri vamale", "suma": 40},  # 0.4% fee
        {"tip": "Taxa vamală", "suma": 1000},
        {"tip": "TVA", "suma": 2200},
    ])
    result = run_fiscal_check(goods, entry)
    assert result["components"]["duty"]["declared"] == Decimal("1000.00")
    assert result["status"] == "PASS"


def test_missing_customs_value_is_uncertain():
    entry = {"duty_rate": Decimal("10")}
    result = run_fiscal_check({"taxe": []}, entry)
    assert result["status"] == "UNCERTAIN"
    assert result["base"] is None
