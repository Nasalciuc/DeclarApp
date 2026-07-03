// Mirrors backend/src/common/models.py - keep the two in sync.

export type DeclarationStatus = "EXTRACTED" | "VALIDATED" | "FLAGGED" | "ERROR";

export interface FiscalComponent {
  status: "MATCH" | "MISMATCH" | "UNCERTAIN";
  expected: number | null;
  declared: number | null;
}

export interface Fiscal {
  status: string;
  base?: number | null;
  components?: Record<string, FiscalComponent>;
  reason?: string;
}

export interface Check {
  status: string;
  issues?: string[];
  reason?: string;
  expected?: number;
  declared?: number;
  value?: string;
}

export interface Semantic {
  status: string;
  confidence?: number;
  reasoning?: string;
  candidate_codes?: { code: string; reason: string }[];
  source?: string;
  previous_status?: string | null;
}

export interface ItemValidation {
  item_number: number;
  format?: Check;
  fiscal?: Fiscal;
  consistency?: Check;
  semantic?: Semantic;
}

export interface TaxRow {
  tip?: string | null;
  baza?: number | null;
  cota?: string | null;
  suma?: number | null;
}

export interface Goods {
  numar_articol?: number | null;
  descriere?: string | null;
  cod_marfa?: string | null;
  tara_origine?: string | null;
  masa_bruta_kg?: number | null;
  masa_neta_kg?: number | null;
  cod_procedura?: string | null;
  valoare_statistica?: number | null;
  pret_articol?: number | null;
  taxe?: TaxRow[];
}

export interface Correction {
  at: string;
  by: string;
  item_number: number;
  old_code?: string | null;
  new_code: string;
  note?: string;
}

export interface Declaration {
  declaration_id: string;
  status: DeclarationStatus;
  s3_key?: string;
  goods_count?: number;
  created_at?: string;
  updated_at?: string;
  error?: string;
  version?: number;
  extracted?: {
    declaratie?: { tip?: string; numar_referinta?: string; data?: string };
    parti?: { importator?: { nume?: string }; exportator?: { nume?: string } };
    financiar?: { valuta?: string; suma_totala_facturata?: number };
    marfuri?: Goods[];
  };
  validation?: {
    items?: ItemValidation[];
    declaration?: Record<string, Check>;
  };
  corrections?: Correction[];
}
