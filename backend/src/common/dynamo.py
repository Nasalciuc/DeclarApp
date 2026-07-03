"""DynamoDB access layer - the only module that talks to the tables.

Table names come from env (DECLARATIONS_TABLE / TARIFF_TABLE) at call time,
so tests and Lambdas configure them the same way.
"""

import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


_RESOURCE = None


def _resource():
    """Lazy, cached per process (one per warm Lambda container)."""
    global _RESOURCE
    if _RESOURCE is None:
        _RESOURCE = boto3.resource("dynamodb")
    return _RESOURCE


def declarations_table():
    return _resource().Table(os.environ.get("DECLARATIONS_TABLE", "declarations"))


def tariff_table():
    return _resource().Table(os.environ.get("TARIFF_TABLE", "tariff_codes"))


def to_dynamo(obj):
    """Recursively convert floats to Decimal (DynamoDB rejects float)."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dynamo(v) for v in obj]
    return obj


def get_tariff_entry(code: str) -> dict | None:
    if not code:
        return None
    return tariff_table().get_item(Key={"code": code}).get("Item")


def get_declaration(declaration_id: str, consistent: bool = True) -> dict | None:
    return declarations_table().get_item(
        Key={"declaration_id": declaration_id},
        ConsistentRead=consistent).get("Item")


def put_new_declaration(record: dict) -> dict:
    """Create/replace a declaration record (idempotent reprocessing).

    Resets optimistic-lock version to 0: re-uploading the same file is a
    deliberate fresh start, not a concurrent edit.
    """
    record = dict(record)
    record["version"] = 0
    declarations_table().put_item(Item=to_dynamo(record))
    return record


def put_declaration_versioned(record: dict) -> dict:
    """Write with optimistic locking on `version`; raises ConflictError."""
    record = dict(record)
    old_version = record.get("version")
    record["version"] = (int(old_version) + 1) if old_version is not None else 1
    condition = (Attr("version").eq(old_version) if old_version is not None
                 else Attr("version").not_exists())
    table = declarations_table()
    try:
        table.put_item(Item=to_dynamo(record), ConditionExpression=condition)
    except table.meta.client.exceptions.ConditionalCheckFailedException as err:
        raise ConflictError(
            "declaration was modified concurrently; reload and retry") from err
    return record
