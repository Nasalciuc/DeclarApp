"""Verdicts and the report JSON - the single source of truth the UI reads."""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from .models import (BAD_STATUSES, REVIEW_STATUSES, DeclarationStatus,
                     iter_check_statuses)

_S3 = None


def _s3():
    global _S3
    if _S3 is None:
        _S3 = boto3.client("s3")
    return _S3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def jsonable(obj):
    """json.dumps default: Decimal -> float."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"not JSON serializable: {type(obj)}")


def compute_verdict(validation: dict) -> str:
    """FLAGGED on any FAIL/MISMATCH, or on any UNCERTAIN; else VALIDATED."""
    statuses = set(iter_check_statuses(validation))
    if statuses & BAD_STATUSES or statuses & REVIEW_STATUSES:
        return DeclarationStatus.FLAGGED
    return DeclarationStatus.VALIDATED


def build_report(record: dict) -> dict:
    return {
        "declaration_id": record.get("declaration_id"),
        "verdict": record.get("status"),
        "checks": record.get("validation") or {},
        "corrections": record.get("corrections") or [],
        "updated_at": record.get("updated_at") or now_iso(),
    }


def write_report(record: dict) -> str | None:
    """Write reports/{id}.json; returns the key, or None when no bucket set."""
    bucket = os.environ.get("REPORTS_BUCKET") or os.environ.get("BUCKET")
    if not bucket:
        return None
    key = f"reports/{record['declaration_id']}.json"
    _s3().put_object(
        Bucket=bucket, Key=key,
        Body=json.dumps(build_report(record), ensure_ascii=False,
                        default=jsonable),
        ContentType="application/json")
    return key
