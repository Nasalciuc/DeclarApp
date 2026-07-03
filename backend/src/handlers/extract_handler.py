"""Lambda: S3 `input/` upload -> Bedrock extraction -> `extracted/` + record.

Failures never poison-loop: the error is written on the record
(status=ERROR) and the event is acknowledged.
"""

import json
from pathlib import PurePosixPath
from urllib.parse import unquote_plus

import boto3

from common import bedrock, dynamo
from common.models import DeclarationStatus
from common.report import now_iso
from prompts.extraction import content_blocks, parse_output


def lambda_handler(event, _context):
    results = []
    for record in event.get("Records") or []:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        if not key.startswith("input/"):
            continue
        declaration_id = PurePosixPath(key).stem
        try:
            _process(bucket, key, declaration_id)
            results.append({"declaration_id": declaration_id, "ok": True})
        except Exception as err:  # noqa: BLE001
            print(f"[extract] {declaration_id} failed: {err}")
            _mark_error(declaration_id, key, str(err))
            results.append({"declaration_id": declaration_id, "ok": False})
    return {"processed": results}


MAX_DOCUMENT_BYTES = 8 * 1024 * 1024  # Bedrock document blocks cap ~4.5 MB;
                                      # reject early, before memory/model cost.


def _process(bucket: str, key: str, declaration_id: str) -> None:
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    size = obj.get("ContentLength") or 0
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError(
            f"document is {size} bytes; max {MAX_DOCUMENT_BYTES} "
            "(Bedrock document limit)")
    raw = obj["Body"].read()
    ext = PurePosixPath(key).suffix

    text = bedrock.converse(content_blocks(raw, ext))
    extracted = parse_output(text)

    # Order matters: write the DynamoDB record BEFORE the extracted/ object.
    # The extracted/ put fires the validate Lambda immediately; if the record
    # landed second, validate could read nothing and the late EXTRACTED write
    # would clobber the verdict.
    dynamo.put_new_declaration({
        "declaration_id": declaration_id,
        "status": DeclarationStatus.EXTRACTED,
        "s3_key": key,
        "created_at": now_iso(),
        "goods_count": len(extracted.get("marfuri") or []),
        "extracted": extracted,
    })

    s3.put_object(
        Bucket=bucket, Key=f"extracted/{declaration_id}.json",
        Body=json.dumps(extracted, ensure_ascii=False),
        ContentType="application/json")


def _mark_error(declaration_id: str, key: str, message: str) -> None:
    try:
        dynamo.put_new_declaration({
            "declaration_id": declaration_id,
            "status": DeclarationStatus.ERROR,
            "s3_key": key,
            "created_at": now_iso(),
            "error": message[:500],
        })
    except Exception as err:  # noqa: BLE001
        print(f"[extract] could not record error for {declaration_id}: {err}")

