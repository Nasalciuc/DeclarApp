"""Deterministic fiscal engine (pure functions, no I/O).

Recomputes duty / excise / VAT for one goods item from a tariff entry and
compares with the declared amounts (SAD box 47).

Rules encoded here:
  - duty       = customs value x duty_rate%          (ad-valorem; specific TODO)
  - excise     = value x rate%  OR  amount x net kg  (per tariff entry)
  - VAT base   = customs value + duty + excise       (MD / EU rule)
  - tolerance  = max(1.00 currency unit, 0.5% of expected)

A missing box-47 row counts as "declared 0" (catches undeclared taxes).
An expected value that cannot be computed from available data -> UNCERTAIN.
"""

from decimal import Decimal, ROUND_HALF_UP

TOLERANCE_REL = Decimal("0.005")
# NOTE: the absolute tolerance is in the DECLARATION currency, so one
# unit is "wider" on EUR/USD documents than on MDL ones. Fine for F1.
TOLERANCE_ABS = Decimal("1.00")
DEFAULT_VAT_RATE = Decimal("20")
CENT = Decimal("0.01")

_TAX_KEYWORDS = {
    "duty":   ("vam", "пошлин", "duty"),
    "vat":    ("tva", "ндс", "vat"),
    "excise": ("acciz", "акциз", "excise"),
}

# Box 47 rows we recognize but deliberately DON'T map to duty: the customs
# procedure fee ("taxa pentru proceduri vamale" / "таможенный сбор") contains
# duty-like keywords yet is a separate levy our engine doesn't recompute.
_NOT_DUTY = ("procedur", "сбор")


def to_decimal(x) -> Decimal | None:
    """Coerce DynamoDB / JSON values to Decimal; None if absent or invalid."""
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x))
    except Exception:  # noqa: BLE001
        return None


def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _declared_taxes(goods_item: dict) -> dict:
    """Parse box-47 rows ('taxe') into {component: {'suma', 'baza'}}."""
    out: dict = {}
    for row in goods_item.get("taxe") or []:
        tip = str(row.get("tip") or "").lower()
        for component, keywords in _TAX_KEYWORDS.items():
            if component == "duty" and any(k in tip for k in _NOT_DUTY):
                continue
            if component not in out and any(k in tip for k in keywords):
                out[component] = {"suma": to_decimal(row.get("suma")),
                                  "baza": to_decimal(row.get("baza"))}
                break
    return out


def _duty_base(goods_item: dict, declared: dict) -> Decimal | None:
    """Customs value: declared duty base -> statistical value -> item price."""
    duty_row = declared.get("duty") or {}
    for candidate in (duty_row.get("baza"),
                      goods_item.get("valoare_statistica"),
                      goods_item.get("pret_articol")):
        value = to_decimal(candidate)
        if value is not None and value > 0:
            return value
    return None


def _expected_excise(entry: dict, goods_item: dict, base: Decimal) -> Decimal | None:
    """None means 'cannot be computed from available data' (-> UNCERTAIN)."""
    excise = entry.get("excise")
    if not excise:
        return Decimal("0")
    rate = to_decimal(excise.get("rate"))
    if rate is not None:
        return base * rate / 100
    amount = to_decimal(excise.get("amount"))
    per = str(excise.get("per") or "").lower()
    if amount is not None and per == "kg":
        qty = to_decimal(goods_item.get("masa_neta_kg"))
        return amount * qty if qty is not None else None
    return None  # per-litre/pair/etc.: quantity not in the extraction schema yet


def compare_amounts(expected: Decimal | None, declared: Decimal | None) -> dict:
    """Tolerance-aware comparison of one amount pair."""
    if expected is None:
        return {"status": "UNCERTAIN", "expected": None,
                "declared": money(declared) if declared is not None else None}
    declared = declared if declared is not None else Decimal("0")
    tolerance = max(TOLERANCE_ABS, expected.copy_abs() * TOLERANCE_REL)
    status = "MATCH" if (declared - expected).copy_abs() <= tolerance else "MISMATCH"
    return {"status": status, "expected": money(expected), "declared": money(declared)}


def run_fiscal_check(goods_item: dict, tariff_entry: dict) -> dict:
    """Full fiscal check for one goods item.

    Returns {"status": PASS|FAIL|UNCERTAIN, "base": ..., "components": {...}}.
    """
    declared = _declared_taxes(goods_item)
    base = _duty_base(goods_item, declared)
    if base is None:
        return {"status": "UNCERTAIN", "base": None, "components": {},
                "reason": "no customs value available for this item"}

    duty_rate = to_decimal(tariff_entry.get("duty_rate"))
    duty_expected = base * duty_rate / 100 if duty_rate is not None else None
    excise_expected = _expected_excise(tariff_entry, goods_item, base)

    vat_rate = to_decimal(tariff_entry.get("vat_rate")) or DEFAULT_VAT_RATE
    if duty_expected is not None and excise_expected is not None:
        vat_expected = (base + duty_expected + excise_expected) * vat_rate / 100
    else:
        vat_expected = None

    components = {
        "duty":   compare_amounts(duty_expected,
                                  (declared.get("duty") or {}).get("suma")),
        "excise": compare_amounts(excise_expected,
                                  (declared.get("excise") or {}).get("suma")),
        "vat":    compare_amounts(vat_expected,
                                  (declared.get("vat") or {}).get("suma")),
    }
    statuses = {c["status"] for c in components.values()}
    overall = ("FAIL" if "MISMATCH" in statuses
               else "UNCERTAIN" if "UNCERTAIN" in statuses
               else "PASS")
    return {"status": overall, "base": money(base), "components": components}
