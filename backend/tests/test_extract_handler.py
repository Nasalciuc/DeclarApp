"""extract_handler on moto: happy path writes extracted/ + record; errors
are recorded, never raised."""

import json
import os

import boto3
from moto import mock_aws

import helpers
from handlers import extract_handler


@mock_aws
def test_upload_produces_extracted_json_and_record(monkeypatch):
    helpers.make_tables()
    bucket = helpers.make_bucket()
    fixture = helpers.load_fixture()
    monkeypatch.setattr(extract_handler.bedrock, "converse",
                        lambda content, **kw: json.dumps(fixture))

    boto3.client("s3").put_object(Bucket=bucket, Key="input/DECL-1.pdf",
                                  Body=b"%PDF-fake")
    result = extract_handler.lambda_handler(
        helpers.s3_event("input/DECL-1.pdf"), None)
    assert result["processed"] == [{"declaration_id": "DECL-1", "ok": True}]

    body = boto3.client("s3").get_object(
        Bucket=bucket, Key="extracted/DECL-1.json")["Body"].read()
    assert json.loads(body)["marfuri"][0]["cod_marfa"] == "85285200"

    record = boto3.resource("dynamodb").Table(
        os.environ["DECLARATIONS_TABLE"]).get_item(
        Key={"declaration_id": "DECL-1"})["Item"]
    assert record["status"] == "EXTRACTED"
    assert record["version"] == 0
    assert record["goods_count"] == 1
    assert record["s3_key"] == "input/DECL-1.pdf"


@mock_aws
def test_bedrock_failure_marks_record_error(monkeypatch):
    helpers.make_tables()
    bucket = helpers.make_bucket()

    def boom(content, **kw):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(extract_handler.bedrock, "converse", boom)
    boto3.client("s3").put_object(Bucket=bucket, Key="input/DECL-2.pdf",
                                  Body=b"%PDF-fake")
    result = extract_handler.lambda_handler(
        helpers.s3_event("input/DECL-2.pdf"), None)
    assert result["processed"][0]["ok"] is False

    record = boto3.resource("dynamodb").Table(
        os.environ["DECLARATIONS_TABLE"]).get_item(
        Key={"declaration_id": "DECL-2"})["Item"]
    assert record["status"] == "ERROR"
    assert "model unavailable" in record["error"]


@mock_aws
def test_non_input_keys_are_ignored(monkeypatch):
    helpers.make_tables()
    helpers.make_bucket()
    monkeypatch.setattr(extract_handler.bedrock, "converse",
                        lambda content, **kw: "{}")
    result = extract_handler.lambda_handler(
        helpers.s3_event("reports/x.json"), None)
    assert result["processed"] == []
