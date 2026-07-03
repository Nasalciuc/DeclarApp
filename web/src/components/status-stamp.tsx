import { STATUS_LABEL } from "@/lib/format";
import type { DeclarationStatus } from "@/lib/types";

const KIND: Record<DeclarationStatus, string> = {
  VALIDATED: "pass",
  FLAGGED: "warn",
  ERROR: "fail",
  EXTRACTED: "wait",
};

export default function StatusStamp({ status }: { status: DeclarationStatus }) {
  const kind = KIND[status] ?? "wait";
  return (
    <span className={`stamp stamp-${kind}`}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
