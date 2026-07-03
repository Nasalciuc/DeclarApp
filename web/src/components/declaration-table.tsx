"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listDeclarations } from "@/actions/declarations";
import { STATUS_LABEL, fmtDate } from "@/lib/format";
import type { Declaration } from "@/lib/types";

export default function DeclarationTable({
  initial,
}: {
  initial: Declaration[];
}) {
  const [rows, setRows] = useState<Declaration[]>(initial);

  useEffect(() => {
    const timer = setInterval(async () => {
      if (document.visibilityState === "hidden") return;
      try {
        setRows(await listDeclarations());
      } catch {
        /* transient - keep the last good list */
      }
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  if (rows.length === 0) {
    return (
      <div className="card empty">
        <p className="muted">Nicio declarație încă.</p>
        <Link href="/upload" className="btn btn-primary">
          Încarcă prima declarație
        </Link>
      </div>
    );
  }

  return (
    <div className="card table-wrap" style={{ marginTop: "1.4rem" }}>
      <table className="table">
        <thead>
          <tr>
            <th>Referință</th>
            <th>Încărcată</th>
            <th>Mărfuri</th>
            <th>Stare</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const count = row.goods_count ?? row.extracted?.marfuri?.length ?? 0;
            const status = row.status?.toLowerCase() ?? "extracted";
            return (
              <tr key={row.declaration_id}>
                <td>
                  <Link
                    href={`/declarations/${row.declaration_id}`}
                    className="row-link mono"
                  >
                    {row.declaration_id}
                  </Link>
                </td>
                <td>{fmtDate(row.created_at)}</td>
                <td>{count || "—"}</td>
                <td>
                  <span
                    className={`chip chip-${status}${
                      row.status === "EXTRACTED" ? " pulse" : ""
                    }`}
                  >
                    {STATUS_LABEL[row.status] ?? row.status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
