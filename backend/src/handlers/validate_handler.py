"""Lambda: S3 `extracted/` event -> the four checks -> report + verdict.

Per goods item: format, fiscal, consistency, and (when ENABLE_SEMANTIC=1)
the semantic description<->code check via Bedrock. Declaration-level:
currency and invoice totals. Everything except semantic is deterministic.
"""

import json
import os
from decimal import Decimal
from pathlib import PurePosixPath
from urllib.parse import unquote_plus

import boto3

from common import bedrock, dynamo
from common.codes import (check_country, check_currency, is_tariff_line,
                          normalize_code)
from common.fiscal import compare_amounts, run_fiscal_check, to_decimal
from common.models import CheckStatus, SemanticStatus
from common.report import compute_verdict, now_iso, write_report
from prompts import semantic


def lambda_handler(event, _context):
    results = []
    for record in event.get("Records") or []:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        if not key.startswith("extracted/") or not key.endswith(".json"):
            continue
        declaration_id = PurePosixPath(key).stem
        _process(bucket, key, declaration_id)
        results.append({"declaration_id": declaration_id})
    return {"processed": results}


def _process(bucket: str, key: str, declaration_id: str) -> None:
    extracted = json.loads(
        boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"]
        .read().decode("utf-8"))

    # Semantic (Bedrock) runs once, outside the write-retry loop.
    validation = validate_declaration(extracted)
    verdict = compute_verdict(validation)
    goods_count = len(extracted.get("marfuri") or [])

    # Optimistic-lock write with retry: a concurrent HITL correction can
    # bump the version between our read and write; re-read and re-apply.
    last_error = None
    for _ in range(3):
        # Normally extract writes the record before this event fires; the
        # fallback covers manual puts into extracted/ (no extension guessing).
        record = dynamo.get_declaration(declaration_id) or {
            "declaration_id": declaration_id,
            "created_at": now_iso(),
        }
        record["extracted"] = extracted
        record["goods_count"] = goods_count
        record["validation"] = validation
        record["status"] = verdict
        record["updated_at"] = now_iso()
        try:
            dynamo.put_declaration_versioned(record)
            write_report(record)
            return
        except dynamo.ConflictError as err:
            last_error = err
    raise last_error


def validate_declaration(extracted: dict, semantic_enabled: bool | None = None) -> dict:
    """Run all checks over one extracted declaration. Pure except semantic."""
    if semantic_enabled is None:
        semantic_enabled = os.environ.get("ENABLE_SEMANTIC", "0") == "1"

    financiar = extracted.get("financiar") or {}
    marfuri = extracted.get("marfuri") or []

    items = []
    for index, goods in enumerate(marfuri):
        number = to_decimal(goods.get("numar_articol"))
        item_number = int(number) if number is not None else index + 1
        code = normalize_code(goods.get("cod_marfa"))
        entry = dynamo.get_tariff_entry(code) if is_tariff_line(code) else None

        item = {
            "item_number": item_number,
            "format": _format_check(goods, code, entry is not None),
            "fiscal": (run_fiscal_check(goods, entry) if entry else
                       {"status": CheckStatus.UNCERTAIN,
                        "reason": "tariff entry unknown; fiscal not computable"}),
            "consistency": _consistency_check(goods),
            "semantic": _semantic_check(goods, entry, semantic_enabled),
        }
        items.append(item)

    return {
        "items": items,
        "declaration": {
            "currency": check_currency(financiar.get("valuta")),
            "totals": _totals_check(marfuri, financiar),
        },
    }


def _format_check(goods: dict, code: str, entry_exists: bool) -> dict:
    issues = []
    if not is_tariff_line(code):
        issues.append(f"tariff code '{goods.get('cod_marfa')}' is not an "
                      "8-9 digit tariff line")
    elif not entry_exists:
        issues.append(f"code {code} not found in the nomenclature")

    country = check_country(goods.get("tara_origine"))
    if country["status"] == CheckStatus.FAIL:
        issues.append(country.get("reason", "invalid origin country"))

    if issues:
        status = CheckStatus.FAIL
    elif country["status"] == CheckStatus.UNCERTAIN:
        status = CheckStatus.UNCERTAIN
    else:
        status = CheckStatus.PASS
    return {"status": status, "issues": issues}


def _consistency_check(goods: dict) -> dict:
    issues = []
    net = to_decimal(goods.get("masa_neta_kg"))
    gross = to_decimal(goods.get("masa_bruta_kg"))
    if net is not None and gross is not None and net > gross:
        issues.append(f"net mass {net} kg exceeds gross mass {gross} kg")
    price = to_decimal(goods.get("pret_articol"))
    if price is not None and price <= 0:
        issues.append("item price is not positive")
    return {"status": CheckStatus.FAIL if issues else CheckStatus.PASS,
            "issues": issues}


def _totals_check(marfuri: list, financiar: dict) -> dict:
    invoice = to_decimal(financiar.get("suma_totala_facturata"))
    if invoice is None:
        return {"status": CheckStatus.SKIPPED,
                "reason": "invoice total not extracted"}
    prices = [to_decimal(g.get("pret_articol")) for g in marfuri]
    if not prices or any(p is None for p in prices):
        return {"status": CheckStatus.UNCERTAIN,
                "reason": "item prices incomplete; totals not comparable"}
    comparison = compare_amounts(sum(prices, Decimal("0")), invoice)
    status = (CheckStatus.PASS if comparison["status"] == "MATCH"
              else CheckStatus.FAIL)
    return {"status": status, "expected": comparison["expected"],
            "declared": comparison["declared"]}


def _semantic_check(goods: dict, entry: dict | None, enabled: bool) -> dict:
    if not enabled:
        return {"status": SemanticStatus.SKIPPED,
                "reason": "semantic check disabled (ENABLE_SEMANTIC=0)"}
    if not entry:
        return {"status": SemanticStatus.UNCERTAIN,
                "reason": "tariff entry unknown; nothing to compare against"}
    if not goods.get("descriere"):
        return {"status": SemanticStatus.UNCERTAIN,
                "reason": "goods description not extracted"}
    try:
        text = bedrock.converse(semantic.build_content(goods, entry),
                                max_tokens=800)
        return semantic.parse_output(text)
    except Exception as err:  # noqa: BLE001
        print(f"[validate] semantic check failed: {err}")
        return {"status": SemanticStatus.UNCERTAIN,
                "reason": "semantic check errored; see logs"}
