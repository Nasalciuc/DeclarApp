"""Lambda: the HITL action behind the "Corectează codul" button.

  1. validates the new tariff code against `tariff_codes` (format re-check)
  2. writes the corrected code into the goods item in `declarations`
  3. re-runs the deterministic FISCAL check against the new tariff entry
  4. updates the item's validation, verdict, audit trail and the S3 report

The semantic check is NOT re-run by an LLM: a deliberate human correction
*is* the semantic resolution -> {"status": "MATCH", "source": "human_correction"}.
"""

import json

from common import dynamo
from common.codes import is_tariff_line, normalize_code
from common.fiscal import run_fiscal_check, to_decimal
from common.models import CheckStatus, SemanticStatus
from common.report import compute_verdict, jsonable, now_iso, write_report


class CorrectionError(Exception):
    """Business error with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def apply_code_correction(declaration_id: str, item_number: int, new_code: str,
                          corrected_by: str, note: str | None = None) -> dict:
    code = normalize_code(new_code)
    if not is_tariff_line(code):
        raise CorrectionError(
            "INVALID_CODE",
            f"'{new_code}' is not a tariff line; expected 8-9 digits")

    entry = dynamo.get_tariff_entry(code)
    if not entry:
        raise CorrectionError("INVALID_CODE",
                              f"code {code} not found in tariff_codes")

    record = dynamo.get_declaration(declaration_id)
    if not record:
        raise CorrectionError("NOT_FOUND",
                              f"declaration {declaration_id} not found")
    if record.get("status") == "EXTRACTED" or not record.get("validation"):
        raise CorrectionError(
            "NOT_VALIDATED",
            "declaration has not been validated yet; wait for the pipeline")

    goods = _find_goods_item(record, int(item_number))
    old_code = goods.get("cod_marfa")
    goods["cod_marfa"] = code

    fiscal = run_fiscal_check(goods, entry)

    validation = record.setdefault("validation", {})
    validation.setdefault("declaration", {})
    item_validation = _get_or_create_item_validation(validation,
                                                     int(item_number))
    previous_semantic = (item_validation.get("semantic") or {}).get("status")
    item_validation["format"] = {"status": CheckStatus.PASS,
                                 "checked": "code_exists",
                                 "source": "human_correction"}
    item_validation["fiscal"] = fiscal
    item_validation["semantic"] = {"status": SemanticStatus.MATCH,
                                   "source": "human_correction",
                                   "previous_status": previous_semantic}

    record["status"] = compute_verdict(validation)
    record["updated_at"] = now_iso()
    record.setdefault("corrections", []).append({
        "at": now_iso(), "by": corrected_by,
        "item_number": int(item_number),
        "old_code": old_code, "new_code": code,
        **({"note": note} if note else {}),
    })

    try:
        record = dynamo.put_declaration_versioned(record)
    except dynamo.ConflictError as err:
        raise CorrectionError("CONFLICT", str(err)) from err

    write_report(record)
    return {
        "declaration_id": declaration_id,
        "item_number": int(item_number),
        "old_code": old_code, "new_code": code,
        "fiscal": fiscal,
        "verdict": record["status"],
        "version": record["version"],
    }


def _find_goods_item(record: dict, item_number: int) -> dict:
    marfuri = (record.get("extracted") or {}).get("marfuri") or []
    for index, goods in enumerate(marfuri):
        number = to_decimal(goods.get("numar_articol"))
        current = int(number) if number is not None else index + 1
        if current == item_number:
            return goods
    raise CorrectionError("ITEM_NOT_FOUND",
                          f"goods item {item_number} not found in declaration")


def _get_or_create_item_validation(validation: dict, item_number: int) -> dict:
    items = validation.setdefault("items", [])
    for entry in items:
        number = to_decimal(entry.get("item_number"))
        if number is not None and int(number) == item_number:
            return entry
    entry = {"item_number": item_number}
    items.append(entry)
    return entry


# --- Lambda entrypoint --------------------------------------------------------
def lambda_handler(event, _context):
    """POST body: {declaration_id, item_number, new_code, corrected_by, note?}"""
    body = event.get("body") if isinstance(event, dict) else None
    payload = json.loads(body) if isinstance(body, str) else (body or event or {})

    missing = [k for k in ("declaration_id", "item_number", "new_code",
                           "corrected_by") if not payload.get(k)]
    if missing:
        return _response(400, {"error": "MISSING_FIELDS", "fields": missing})

    try:
        result = apply_code_correction(
            declaration_id=str(payload["declaration_id"]),
            item_number=int(payload["item_number"]),
            new_code=str(payload["new_code"]),
            corrected_by=str(payload["corrected_by"]),
            note=payload.get("note"))
        return _response(200, result)
    except CorrectionError as err:
        status = {"NOT_FOUND": 404, "ITEM_NOT_FOUND": 404,
                  "CONFLICT": 409, "NOT_VALIDATED": 409}.get(err.code, 400)
        return _response(status, {"error": err.code, "message": err.message})
    except Exception as err:  # noqa: BLE001
        print(f"[hitl_correction] unexpected: {err}")
        return _response(500, {"error": "INTERNAL", "message": "unexpected error"})


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False, default=jsonable),
    }
