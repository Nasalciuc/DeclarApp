"use client";

import { useState, useTransition } from "react";
import { correctCode } from "@/actions/corrections";
import { CHECK_LABEL, chipKind, fmtDate, fmtMoney } from "@/lib/format";
import type {
  Check,
  Declaration,
  Fiscal,
  ItemValidation,
  Semantic,
} from "@/lib/types";

const FISCAL_LABEL: Record<string, string> = {
  duty: "Taxă vamală",
  excise: "Acciz",
  vat: "TVA",
};

function Chip({ status }: { status?: string }) {
  return (
    <span className={`chip chip-${chipKind(status)}`}>
      {CHECK_LABEL[status ?? ""] ?? status ?? "—"}
    </span>
  );
}

function goodsFor(decl: Declaration, itemNumber: number) {
  const list = decl.extracted?.marfuri ?? [];
  // No fallback to list[0]: showing the wrong item silently is worse
  // than showing "-" when the numbering does not line up.
  return list.find((g, i) => (g.numar_articol ?? i + 1) === itemNumber);
}

export default function ChecksPanel({
  declaration,
  currency,
}: {
  declaration: Declaration;
  currency: string;
}) {
  const items = declaration.validation?.items ?? [];
  const decl = declaration.validation?.declaration ?? {};

  return (
    <div>
      <DeclarationChecks decl={decl} currency={currency} />
      {items.map((item) => (
        <ItemCard
          key={item.item_number}
          item={item}
          currency={currency}
          declarationId={declaration.declaration_id}
          description={goodsFor(declaration, item.item_number)?.descriere}
          code={goodsFor(declaration, item.item_number)?.cod_marfa}
        />
      ))}
      <History corrections={declaration.corrections ?? []} />
    </div>
  );
}

function DeclarationChecks({
  decl,
  currency,
}: {
  decl: Record<string, Check>;
  currency: string;
}) {
  const currencyCheck = decl.currency;
  const totals = decl.totals;
  if (!currencyCheck && !totals) return null;
  return (
    <div className="card">
      <p className="eyebrow">nivel declarație</p>
      <div className="decl-checks" style={{ marginTop: ".5rem" }}>
        {currencyCheck && (
          <span className="pair">
            Valută <Chip status={currencyCheck.status} />
            {currencyCheck.value && (
              <span className="mono muted">{currencyCheck.value}</span>
            )}
          </span>
        )}
        {totals && (
          <span className="pair">
            Total factură <Chip status={totals.status} />
            {totals.expected !== undefined && (
              <span className="muted">
                {fmtMoney(totals.declared, currency)} vs{" "}
                {fmtMoney(totals.expected, currency)}
              </span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}

function ItemCard({
  item,
  currency,
  declarationId,
  description,
  code,
}: {
  item: ItemValidation;
  currency: string;
  declarationId: string;
  description?: string | null;
  code?: string | null;
}) {
  const needsFix =
    item.format?.status === "FAIL" ||
    item.fiscal?.status === "FAIL" ||
    item.semantic?.status === "MISMATCH";

  return (
    <div className="card">
      <div className="item-head">
        <p className="eyebrow">marfa {item.item_number} · caseta 33</p>
        <span className="mono" style={{ fontWeight: 600 }}>
          {code ?? "—"}
        </span>
      </div>
      {description && <p className="item-desc">{description}</p>}

      <CheckRow name="Format" status={item.format?.status}>
        {item.format?.issues && item.format.issues.length > 0 && (
          <ul className="issues">
            {item.format.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        )}
      </CheckRow>

      <CheckRow name="Fiscal" status={item.fiscal?.status}>
        <FiscalTable fiscal={item.fiscal} currency={currency} />
      </CheckRow>

      <CheckRow name="Consistență" status={item.consistency?.status}>
        {item.consistency?.issues && item.consistency.issues.length > 0 && (
          <ul className="issues">
            {item.consistency.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        )}
      </CheckRow>

      <CheckRow name="Semantic" status={item.semantic?.status}>
        <SemanticBody semantic={item.semantic} />
      </CheckRow>

      {needsFix && (
        <CorrectionForm
          declarationId={declarationId}
          itemNumber={item.item_number}
          suggested={item.semantic?.candidate_codes?.[0]?.code}
        />
      )}
    </div>
  );
}

function CheckRow({
  name,
  status,
  children,
}: {
  name: string;
  status?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="check-row">
      <div className="check-body">
        <div className="check-head">
          <p className="check-name">{name}</p>
          <Chip status={status} />
        </div>
        {children}
      </div>
    </div>
  );
}

function FiscalTable({
  fiscal,
  currency,
}: {
  fiscal?: Fiscal;
  currency: string;
}) {
  if (!fiscal) return null;
  if (!fiscal.components) {
    return fiscal.reason ? <p className="issues">{fiscal.reason}</p> : null;
  }
  return (
    <table className="fisc-table">
      <thead>
        <tr>
          <th>Componentă</th>
          <th>Declarat</th>
          <th>Calculat</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(fiscal.components).map(([key, c]) => (
          <tr key={key} className={c.status === "MISMATCH" ? "delta-bad" : ""}>
            <td>{FISCAL_LABEL[key] ?? key}</td>
            <td>{fmtMoney(c.declared, currency)}</td>
            <td>{fmtMoney(c.expected, currency)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SemanticBody({ semantic }: { semantic?: Semantic }) {
  if (!semantic) return null;
  if (semantic.source === "human_correction") {
    return <p className="issues">Confirmat prin corectare umană.</p>;
  }
  return (
    <div>
      {semantic.reasoning && <p className="issues">{semantic.reasoning}</p>}
      {typeof semantic.confidence === "number" && (
        <p className="muted" style={{ margin: ".3rem 0 0" }}>
          Încredere {Math.round(semantic.confidence * 100)}%
        </p>
      )}
      {semantic.candidate_codes && semantic.candidate_codes.length > 0 && (
        <p style={{ margin: ".45rem 0 0" }}>
          <span className="muted">Coduri sugerate: </span>
          {semantic.candidate_codes.map((c) => (
            <span
              key={c.code}
              className="chip chip-skip mono"
              style={{ marginRight: ".35rem" }}
              title={c.reason}
            >
              {c.code}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

function CorrectionForm({
  declarationId,
  itemNumber,
  suggested,
}: {
  declarationId: string;
  itemNumber: number;
  suggested?: string;
}) {
  const [code, setCode] = useState(suggested ?? "");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<
    { ok: boolean; message?: string } | null
  >(null);
  const [pending, startTransition] = useTransition();

  function submit() {
    setResult(null);
    startTransition(async () => {
      const r = await correctCode({
        declarationId,
        itemNumber,
        newCode: code.trim(),
        note: note.trim() || undefined,
      });
      setResult({
        ok: r.ok,
        message: r.ok
          ? `Cod corectat. Verdict nou: ${r.verdict}.`
          : r.message,
      });
    });
  }

  return (
    <div className="correct-box">
      <p className="eyebrow" style={{ marginBottom: ".5rem" }}>
        corectează codul
      </p>
      <div className="form-row">
        <input
          className="input code mono"
          placeholder="ex. 84713000"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label="Cod tarifar nou"
        />
        <input
          className="input note"
          placeholder="Notă (opțional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          aria-label="Notă"
        />
        <button
          className="btn btn-primary"
          onClick={submit}
          disabled={pending || code.trim().length < 8}
        >
          {pending ? "Se aplică…" : "Corectează codul"}
        </button>
      </div>
      {result && (
        <p className={result.ok ? "result-ok" : "result-err"}>
          {result.message}
        </p>
      )}
    </div>
  );
}

function History({
  corrections,
}: {
  corrections: Declaration["corrections"];
}) {
  if (!corrections || corrections.length === 0) return null;
  return (
    <div className="card history">
      <p className="eyebrow">istoric corectări</p>
      <ul style={{ listStyle: "none", padding: 0, margin: ".5rem 0 0" }}>
        {corrections.map((c, i) => (
          <li key={i}>
            <span className="muted">{fmtDate(c.at)}</span> · {c.by} ·{" "}
            <span className="mono">
              {c.old_code ?? "—"} → {c.new_code}
            </span>
            {c.note ? ` · ${c.note}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
