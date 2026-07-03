"""Shared moto helpers for handler tests."""

import json
import os
from decimal import Decimal
from pathlib import Path

import boto3

FIXTURE = Path(__file__).parent / "fixtures" / "declaration_sample.json"
REGION = "eu-central-1"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_bucket(name: str | None = None) -> str:
    name = name or os.environ["BUCKET"]
    boto3.client("s3").create_bucket(
        Bucket=name,
        CreateBucketConfiguration={"LocationConstraint": REGION})
    return name


def make_tables():
    ddb = boto3.resource("dynamodb")
    ddb.create_table(
        TableName=os.environ["TARIFF_TABLE"],
        KeySchema=[{"AttributeName": "code", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "code", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST")
    ddb.create_table(
        TableName=os.environ["DECLARATIONS_TABLE"],
        KeySchema=[{"AttributeName": "declaration_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "declaration_id",
                               "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST")
    return ddb


def seed_tariff():
    table = boto3.resource("dynamodb").Table(os.environ["TARIFF_TABLE"])
    table.put_item(Item={"code": "85285200", "description_ro": "Monitoare",
                         "duty_rate": Decimal("10"),
                         "vat_rate": Decimal("20")})
    table.put_item(Item={"code": "84713000",
                         "description_ro": "Mașini de calcul portabile",
                         "duty_rate": Decimal("0"),
                         "vat_rate": Decimal("20")})


def s3_event(key: str, bucket: str | None = None) -> dict:
    return {"Records": [{"s3": {
        "bucket": {"name": bucket or os.environ["BUCKET"]},
        "object": {"key": key}}}]}
