"""HITL correction on moto - adapted to the per-item validation structure."""

import json
import os
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

import helpers
from handlers import hitl_correction as hc


def _seed_declaration(declaration_id="MD-2026-08412", taxes=None):
    """Item declared under the WRONG code 85285200 (monitors, 10% duty)."""
    if taxes is None:
        taxes = [
            {"tip": "Taxa vamală", "baza": Decimal("24300"),
             "cota": "10%", "suma": Decimal("2430.00")},
            {"tip": "TVA", "baza": Decimal("26730"),
             "cota": "20%", "suma": Decimal("5346.00")},
        ]
    boto3.resource("dynamodb").Table(os.environ["DECLARATIONS_TABLE"]).put_item(
        Item={
            "declaration_id": declaration_id,
            "status": "FLAGGED",
            "extracted": {"marfuri": [{
                "numar_articol": Decimal("1"),
                "descriere": "Laptop 15.6, 16 GB RAM",
                "cod_marfa": "85285200",
                "tara_origine": "CN",
                "masa_neta_kg": Decimal("42.0"),
                "valoare_statistica": Decimal("24300"),
                "taxe": taxes,
            }]},
            "validation": {
                "items": [{
                    "item_number": Decimal("1"),
                    "consistency": {"status": "PASS"},
                    "semantic": {"status": "MISMATCH",
                                 "confidence": Decimal("0.87")},
                }],
                "declaration": {"currency": {"status": "PASS"}},
            },
        })


@mock_aws
def test_correction_recomputes_fiscal_and_flags_wrong_taxes():
    helpers.make_tables()
    helpers.seed_tariff()
    helpers.make_bucket()
    _seed_declaration()

    result = hc.apply_code_correction(
        "MD-2026-08412", 1, "8471.30 00", corrected_by="broker@firma.md")

    assert result["new_code"] == "84713000"
    assert result["old_code"] == "85285200"

    components = result["fiscal"]["components"]
    assert components["duty"] == {"status": "MISMATCH",
                                  "expected": Decimal("0.00"),
                                  "declared": Decimal("2430.00")}
    assert components["vat"] == {"status": "MISMATCH",
                                 "expected": Decimal("4860.00"),
                                 "declared": Decimal("5346.00")}
    assert result["fiscal"]["status"] == "FAIL"
    assert result["verdict"] == "FLAGGED"

    saved = boto3.resource("dynamodb").Table(
        os.environ["DECLARATIONS_TABLE"]).get_item(
        Key={"declaration_id": "MD-2026-08412"})["Item"]
    assert saved["extracted"]["marfuri"][0]["cod_marfa"] == "84713000"
    item = saved["validation"]["items"][0]
    assert item["semantic"]["status"] == "MATCH"
    assert item["semantic"]["source"] == "human_correction"
    assert item["semantic"]["previous_status"] == "MISMATCH"
    assert saved["corrections"][0]["by"] == "broker@firma.md"
    assert saved["version"] == 1

    report = json.loads(boto3.client("s3").get_object(
        Bucket=os.environ["REPORTS_BUCKET"],
        Key="reports/MD-2026-08412.json")["Body"].read())
    assert report["verdict"] == "FLAGGED"
    assert (report["checks"]["items"][0]["fiscal"]["components"]["vat"]
            ["expected"] == 4860.0)


@mock_aws
def test_correct_taxes_within_tolerance_validate():
    helpers.make_tables()
    helpers.seed_tariff()
    helpers.make_bucket()
    # Declared taxes already match the laptop code: duty absent (=0),
    # VAT 4862 vs expected 4860 -> inside max(1, 0.5%) tolerance.
    _seed_declaration(taxes=[
        {"tip": "TVA", "baza": Decimal("24300"),
         "cota": "20%", "suma": Decimal("4862.00")},
    ])

    result = hc.apply_code_correction(
        "MD-2026-08412", 1, "84713000", corrected_by="broker@firma.md")

    components = result["fiscal"]["components"]
    assert components["duty"]["status"] == "MATCH"   # missing row == 0
    assert components["vat"]["status"] == "MATCH"    # 2 MDL delta, tolerated
    assert result["fiscal"]["status"] == "PASS"
    assert result["verdict"] == "VALIDATED"


@mock_aws
def test_unknown_or_short_code_rejected():
    helpers.make_tables()
    helpers.seed_tariff()
    helpers.make_bucket()
    _seed_declaration()

    with pytest.raises(hc.CorrectionError) as err:
        hc.apply_code_correction("MD-2026-08412", 1, "9999.99 99", "x@y.md")
    assert err.value.code == "INVALID_CODE"

    with pytest.raises(hc.CorrectionError) as err:
        hc.apply_code_correction("MD-2026-08412", 1, "8471.30", "x@y.md")
    assert "8-9 digits" in err.value.message  # heading-level, not a line


@mock_aws
def test_lambda_handler_roundtrip_and_versioning():
    helpers.make_tables()
    helpers.seed_tariff()
    helpers.make_bucket()
    _seed_declaration()

    response = hc.lambda_handler({"body": json.dumps({
        "declaration_id": "MD-2026-08412", "item_number": 1,
        "new_code": "84713000", "corrected_by": "broker@firma.md",
        "note": "confirmat cu factura",
    })}, None)
    assert response["statusCode"] == 200
    payload = json.loads(response["body"])
    assert payload["verdict"] == "FLAGGED"

    second = hc.apply_code_correction(
        "MD-2026-08412", 1, "85285200", corrected_by="sef@firma.md")
    assert second["version"] == 2


@mock_aws
def test_correction_refused_before_validation():
    helpers.make_tables()
    helpers.seed_tariff()
    helpers.make_bucket()
    boto3.resource("dynamodb").Table(os.environ["DECLARATIONS_TABLE"]).put_item(
        Item={"declaration_id": "EARLY-1", "status": "EXTRACTED",
              "extracted": {"marfuri": [{"numar_articol": Decimal("1"),
                                         "cod_marfa": "85285200"}]}})
    with pytest.raises(hc.CorrectionError) as err:
        hc.apply_code_correction("EARLY-1", 1, "84713000", "x@y.md")
    assert err.value.code == "NOT_VALIDATED"

    response = hc.lambda_handler({"body": json.dumps({
        "declaration_id": "EARLY-1", "item_number": 1,
        "new_code": "84713000", "corrected_by": "x@y.md"})}, None)
    assert response["statusCode"] == 409
