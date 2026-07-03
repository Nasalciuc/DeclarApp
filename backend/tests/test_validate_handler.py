"""validate_handler on moto: verdicts, report, and semantic wiring."""

import json
import os

import boto3
from moto import mock_aws

import helpers
from handlers import validate_handler


def _put_extracted(bucket: str, declaration_id: str, extracted: dict):
    boto3.client("s3").put_object(
        Bucket=bucket, Key=f"extracted/{declaration_id}.json",
        Body=json.dumps(extracted, ensure_ascii=False))


def _record(declaration_id: str) -> dict:
    return boto3.resource("dynamodb").Table(
        os.environ["DECLARATIONS_TABLE"]).get_item(
        Key={"declaration_id": declaration_id})["Item"]


@mock_aws
def test_correct_declaration_is_validated():
    helpers.make_tables()
    helpers.seed_tariff()
    bucket = helpers.make_bucket()
    _put_extracted(bucket, "OK-1", helpers.load_fixture())

    validate_handler.lambda_handler(helpers.s3_event("extracted/OK-1.json"),
                                    None)

    record = _record("OK-1")
    assert record["status"] == "VALIDATED"
    item = record["validation"]["items"][0]
    assert item["format"]["status"] == "PASS"
    assert item["fiscal"]["status"] == "PASS"
    assert item["consistency"]["status"] == "PASS"
    assert item["semantic"]["status"] == "SKIPPED"
    assert record["validation"]["declaration"]["totals"]["status"] == "PASS"
    assert record["validation"]["declaration"]["currency"]["status"] == "PASS"

    report = json.loads(boto3.client("s3").get_object(
        Bucket=bucket, Key="reports/OK-1.json")["Body"].read())
    assert report["verdict"] == "VALIDATED"


@mock_aws
def test_wrong_taxes_unknown_code_and_bad_masses_flag():
    helpers.make_tables()
    helpers.seed_tariff()
    bucket = helpers.make_bucket()
    extracted = helpers.load_fixture()
    goods = extracted["marfuri"][0]
    goods["taxe"][1]["suma"] = 4000            # wrong VAT
    goods["masa_neta_kg"] = 50.0               # net > gross (45)
    extracted["marfuri"].append({               # second item: unknown code
        "numar_articol": 2, "descriere": "Cabluri",
        "cod_marfa": "99999999", "tara_origine": "CN",
        "pret_articol": 100, "taxe": []})
    extracted["financiar"]["suma_totala_facturata"] = 24400  # 24300 + 100
    _put_extracted(bucket, "BAD-1", extracted)

    validate_handler.lambda_handler(helpers.s3_event("extracted/BAD-1.json"),
                                    None)

    record = _record("BAD-1")
    assert record["status"] == "FLAGGED"
    first, second = record["validation"]["items"]
    assert first["fiscal"]["status"] == "FAIL"
    assert first["fiscal"]["components"]["vat"]["status"] == "MISMATCH"
    assert first["consistency"]["status"] == "FAIL"
    assert second["format"]["status"] == "FAIL"
    assert second["fiscal"]["status"] == "UNCERTAIN"
    assert record["validation"]["declaration"]["totals"]["status"] == "PASS"


@mock_aws
def test_totals_mismatch_flags():
    helpers.make_tables()
    helpers.seed_tariff()
    bucket = helpers.make_bucket()
    extracted = helpers.load_fixture()
    extracted["financiar"]["suma_totala_facturata"] = 30000
    _put_extracted(bucket, "TOT-1", extracted)

    validate_handler.lambda_handler(helpers.s3_event("extracted/TOT-1.json"),
                                    None)
    record = _record("TOT-1")
    assert record["validation"]["declaration"]["totals"]["status"] == "FAIL"
    assert record["status"] == "FLAGGED"


@mock_aws
def test_semantic_mismatch_flags_when_enabled(monkeypatch):
    helpers.make_tables()
    helpers.seed_tariff()
    bucket = helpers.make_bucket()
    _put_extracted(bucket, "SEM-1", helpers.load_fixture())

    monkeypatch.setenv("ENABLE_SEMANTIC", "1")
    monkeypatch.setattr(
        validate_handler.bedrock, "converse",
        lambda content, **kw: json.dumps({
            "status": "MISMATCH", "confidence": 0.87,
            "reasoning": "descrierea e de laptop, codul e de monitoare",
            "candidate_codes": [{"code": "8471.30 00", "reason": "laptop"}]}))

    validate_handler.lambda_handler(helpers.s3_event("extracted/SEM-1.json"),
                                    None)
    record = _record("SEM-1")
    semantic = record["validation"]["items"][0]["semantic"]
    assert semantic["status"] == "MISMATCH"
    assert semantic["candidate_codes"][0]["code"] == "84713000"  # normalized
    assert record["status"] == "FLAGGED"


@mock_aws
def test_concurrent_write_conflict_is_retried(monkeypatch):
    helpers.make_tables()
    helpers.seed_tariff()
    bucket = helpers.make_bucket()
    _put_extracted(bucket, "RACE-1", helpers.load_fixture())

    real_put = validate_handler.dynamo.put_declaration_versioned
    calls = {"n": 0}

    def flaky(record):
        calls["n"] += 1
        if calls["n"] == 1:
            raise validate_handler.dynamo.ConflictError("simulated concurrent edit")
        return real_put(record)

    monkeypatch.setattr(validate_handler.dynamo,
                        "put_declaration_versioned", flaky)
    validate_handler.lambda_handler(helpers.s3_event("extracted/RACE-1.json"),
                                    None)
    assert calls["n"] == 2
    assert _record("RACE-1")["status"] == "VALIDATED"
