"use server";

import { InvokeCommand } from "@aws-sdk/client-lambda";
import { revalidatePath } from "next/cache";
import { HITL_FUNCTION_NAME, lambda } from "@/lib/aws";

export interface CorrectionResult {
  ok: boolean;
  verdict?: string;
  message?: string;
}

/** The button behind the HITL screen: invokes the hitl-correction Lambda. */
export async function correctCode(input: {
  declarationId: string;
  itemNumber: number;
  newCode: string;
  note?: string;
}): Promise<CorrectionResult> {
  if (!HITL_FUNCTION_NAME) {
    return { ok: false, message: "HITL_FUNCTION_NAME nu este configurat." };
  }
  const payload = {
    declaration_id: input.declarationId,
    item_number: input.itemNumber,
    new_code: input.newCode,
    corrected_by: process.env.CORRECTED_BY ?? "broker@local",
    ...(input.note ? { note: input.note } : {}),
  };
  const response = await lambda.send(
    new InvokeCommand({
      FunctionName: HITL_FUNCTION_NAME,
      Payload: Buffer.from(JSON.stringify(payload)),
    }),
  );
  const raw = Buffer.from(response.Payload ?? new Uint8Array()).toString();
  const envelope = raw ? JSON.parse(raw) : {};
  const data =
    typeof envelope.body === "string" ? JSON.parse(envelope.body) : envelope;

  if (envelope.statusCode && envelope.statusCode >= 400) {
    return {
      ok: false,
      message: data.message ?? data.error ?? "Corectarea a eșuat.",
    };
  }
  revalidatePath(`/declarations/${input.declarationId}`);
  revalidatePath("/");
  return { ok: true, verdict: data.verdict };
}
