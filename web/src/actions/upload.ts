"use server";

import { randomUUID } from "crypto";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { BUCKET, s3 } from "@/lib/aws";

const ALLOWED: Record<string, string> = {
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
};

export type UploadTicket =
  | { id: string; url: string; contentType: string }
  | { error: string };

/**
 * Presigned PUT into `input/{uuid}{ext}` - the browser uploads straight to
 * S3 and the pipeline starts on its own from the S3 event.
 */
export async function createUpload(filename: string): Promise<UploadTicket> {
  const ext = ("." + (filename.split(".").pop() ?? "")).toLowerCase();
  const contentType = ALLOWED[ext];
  if (!contentType) {
    return { error: "Format nepermis. Formate acceptate: PDF, PNG, JPG." };
  }
  const id = randomUUID();
  const url = await getSignedUrl(
    s3,
    new PutObjectCommand({
      Bucket: BUCKET,
      Key: `input/${id}${ext}`,
      ContentType: contentType,
    }),
    { expiresIn: 600 },
  );
  return { id, url, contentType };
}
