export function fmtMoney(value: number | null | undefined, currency = "MDL"): string {
  if (value === null || value === undefined) return "—";
  const formatted = new Intl.NumberFormat("ro-MD", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted} ${currency}`;
}

export function fmtDate(iso?: string): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("ro-MD", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export const STATUS_LABEL: Record<string, string> = {
  EXTRACTED: "în procesare",
  VALIDATED: "validat",
  FLAGGED: "de verificat",
  ERROR: "eroare",
};

/** Map any check/semantic status to a visual kind (chip class suffix). */
export function chipKind(status?: string): "pass" | "fail" | "warn" | "skip" {
  switch (status) {
    case "PASS":
    case "MATCH":
      return "pass";
    case "FAIL":
    case "MISMATCH":
      return "fail";
    case "UNCERTAIN":
      return "warn";
    default:
      return "skip";
  }
}

export const CHECK_LABEL: Record<string, string> = {
  PASS: "corect",
  FAIL: "greșit",
  UNCERTAIN: "incert",
  SKIPPED: "omis",
  MATCH: "se potrivește",
  MISMATCH: "nu se potrivește",
};
