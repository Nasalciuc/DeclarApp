"use server";

import { GetCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { BUCKET, DECLARATIONS_TABLE, ddb, s3 } from "@/lib/aws";
import type { Declaration, DeclarationStatus } from "@/lib/types";

const STATUSES: DeclarationStatus[] = [
  "EXTRACTED",
  "VALIDATED",
  "FLAGGED",
  "ERROR",
];

/**
 * Newest-first list via the status-created_at GSI (a Scan with Limit would
 * silently drop the newest rows past ~100 items). Slim projection: the list
 * never ships full extractions over the wire.
 */
export async function listDeclarations(): Promise<Declaration[]> {
  const results = await Promise.all(
    STATUSES.map((status) =>
      ddb.send(
        new QueryCommand({
          TableName: DECLARATIONS_TABLE,
          IndexName: "status-created_at",
          KeyConditionExpression: "#st = :s",
          ExpressionAttributeNames: { "#st": "status" },
          ExpressionAttributeValues: { ":s": status },
          ScanIndexForward: false, // newest first per status
          Limit: 50,
          ProjectionExpression:
            "declaration_id, created_at, updated_at, goods_count, #st",
        }),
      ),
    ),
  );
  const items = results.flatMap((r) => (r.Items ?? []) as Declaration[]);
  return items
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    .slice(0, 100);
}

export async function getDeclaration(id: string): Promise<Declaration | null> {
  const out = await ddb.send(
    new GetCommand({
      TableName: DECLARATIONS_TABLE,
      Key: { declaration_id: id },
    }),
  );
  return (out.Item as Declaration) ?? null;
}

/**
 * Presigned GET for the uploaded document (1h). Only `input/` keys are
 * presignable from the client - never reports or arbitrary bucket paths.
 */
export async function getDocumentUrl(key: string): Promise<string | null> {
  if (!key.startsWith("input/") || key.includes("..")) return null;
  return getSignedUrl(s3, new GetObjectCommand({ Bucket: BUCKET, Key: key }), {
    expiresIn: 3600,
  });
}
