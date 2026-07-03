import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { LambdaClient } from "@aws-sdk/client-lambda";
import { S3Client } from "@aws-sdk/client-s3";

// Vercel reserves the AWS_* env var names (it runs on AWS itself), so the
// app reads APP_AWS_* first and falls back to the default provider chain
// locally (aws configure / AWS_PROFILE).
const region =
  process.env.APP_AWS_REGION ?? process.env.AWS_REGION ?? "eu-central-1";

const credentials =
  process.env.APP_AWS_ACCESS_KEY_ID && process.env.APP_AWS_SECRET_ACCESS_KEY
    ? {
        accessKeyId: process.env.APP_AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.APP_AWS_SECRET_ACCESS_KEY,
      }
    : undefined;

export const s3 = new S3Client({ region, credentials });
export const lambda = new LambdaClient({ region, credentials });
export const ddb = DynamoDBDocumentClient.from(
  new DynamoDBClient({ region, credentials }),
  { marshallOptions: { removeUndefinedValues: true } },
);

export const BUCKET = process.env.BUCKET ?? "";
export const DECLARATIONS_TABLE =
  process.env.DECLARATIONS_TABLE ?? "declarations";
export const HITL_FUNCTION_NAME = process.env.HITL_FUNCTION_NAME ?? "";
