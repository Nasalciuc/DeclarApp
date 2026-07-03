"""Shared vocabulary: statuses and record shapes used across the system."""

from typing import TypedDict


class DeclarationStatus:
    EXTRACTED = "EXTRACTED"
    VALIDATED = "VALIDATED"
    FLAGGED = "FLAGGED"
    ERROR = "ERROR"


class CheckStatus:
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    SKIPPED = "SKIPPED"


class SemanticStatus:
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNCERTAIN = "UNCERTAIN"
    SKIPPED = "SKIPPED"


# Any of these on any check flags the declaration for human review.
BAD_STATUSES = {CheckStatus.FAIL, SemanticStatus.MISMATCH}
REVIEW_STATUSES = {CheckStatus.UNCERTAIN}


class CheckResult(TypedDict, total=False):
    status: str
    issues: list
    reason: str


class ItemValidation(TypedDict, total=False):
    item_number: int
    format: CheckResult
    fiscal: dict
    consistency: CheckResult
    semantic: dict


class Validation(TypedDict, total=False):
    items: list          # list[ItemValidation]
    declaration: dict    # cross-item checks: currency, totals


class DeclarationRecord(TypedDict, total=False):
    declaration_id: str
    status: str
    s3_key: str
    created_at: str
    updated_at: str
    extracted: dict
    validation: Validation
    corrections: list
    version: int
    error: str


def iter_check_statuses(validation: dict) -> "list[str]":
    """Flatten every check status in a validation payload (for verdicts)."""
    statuses: list[str] = []
    for item in validation.get("items") or []:
        for key in ("format", "fiscal", "consistency", "semantic"):
            status = (item.get(key) or {}).get("status")
            if status:
                statuses.append(status)
    for check in (validation.get("declaration") or {}).values():
        if isinstance(check, dict) and check.get("status"):
            statuses.append(check["status"])
    return statuses
