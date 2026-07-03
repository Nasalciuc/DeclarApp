"""[F3] Lambda: suggest plausible tariff codes when semantic gives MISMATCH.

Flow: goods description -> Titan embedding -> k-NN over the nomenclature
descriptions in S3 Vectors -> Claude ranks candidates (with duty impact).

Requires (Phase 3 setup, not part of the F1 stack):
  VECTOR_BUCKET / VECTOR_INDEX  - S3 Vectors bucket + index over tariff_codes
                                  descriptions (metadata: {"code": ...})
  EMBED_MODEL_ID                - default amazon.titan-embed-text-v2:0
"""

import json
import os

import boto3

from common import bedrock, dynamo
from common.fiscal import to_decimal
from prompts.semantic import parse_output as parse_ranking  # same JSON shape

RANK_PROMPT = """You are a customs classification assistant.

Goods description:
\"\"\"{description}\"\"\"

Candidate tariff codes from the nomenclature (with official descriptions
and duty rates):
{candidates}

Pick the most plausible codes for this description, best first.
Return ONLY JSON: {{"status": "MATCH", "confidence": 0-1,
"reasoning": "short", "candidate_codes": [{{"code": "...", "reason": "short"}}]}}
"""


def _embed(text: str) -> list:
    client = boto3.client("bedrock-runtime")
    response = client.invoke_model(
        modelId=os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"),
        body=json.dumps({"inputText": text[:8000]}))
    return json.loads(response["body"].read())["embedding"]


def _knn(embedding: list, top_k: int = 8) -> list:
    """Nearest nomenclature entries from S3 Vectors -> [code, ...]."""
    client = boto3.client("s3vectors")
    response = client.query_vectors(
        vectorBucketName=os.environ["VECTOR_BUCKET"],
        indexName=os.environ["VECTOR_INDEX"],
        queryVector={"float32": embedding},
        topK=top_k, returnMetadata=True)
    codes = []
    for vector in response.get("vectors") or []:
        code = (vector.get("metadata") or {}).get("code")
        if code:
            codes.append(str(code))
    return codes


def suggest(description: str) -> dict:
    """Standalone suggestion for a free-text goods description."""
    candidates = []
    for code in _knn(_embed(description)):
        entry = dynamo.get_tariff_entry(code) or {}
        candidates.append(
            f"- {code}: {entry.get('description_ro') or ''} "
            f"(duty {to_decimal(entry.get('duty_rate')) or '?'}%)")
    if not candidates:
        return {"status": "UNCERTAIN", "confidence": 0,
                "reasoning": "no vector candidates found", "candidate_codes": []}
    text = bedrock.converse(
        [{"text": RANK_PROMPT.format(description=description,
                                     candidates="\n".join(candidates))}],
        max_tokens=800)
    return parse_ranking(text)


def lambda_handler(event, _context):
    """POST body: {declaration_id, item_number} or {description}."""
    body = event.get("body") if isinstance(event, dict) else None
    payload = json.loads(body) if isinstance(body, str) else (body or event or {})

    description = payload.get("description")
    if not description and payload.get("declaration_id"):
        record = dynamo.get_declaration(str(payload["declaration_id"])) or {}
        wanted = int(payload.get("item_number") or 1)
        for index, goods in enumerate((record.get("extracted") or {})
                                      .get("marfuri") or []):
            number = to_decimal(goods.get("numar_articol"))
            if (int(number) if number is not None else index + 1) == wanted:
                description = goods.get("descriere")
                break
    if not description:
        return {"statusCode": 400,
                "body": json.dumps({"error": "MISSING_DESCRIPTION"})}

    result = suggest(str(description))
    return {"statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result, ensure_ascii=False)}
