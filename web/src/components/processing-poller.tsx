"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { getDeclaration } from "@/actions/declarations";

/**
 * Polls the declaration and refreshes the page when it moves on.
 * - waitForRecord: record doesn't exist yet (just uploaded) -> refresh
 *   as soon as extract creates it.
 * - otherwise: record is EXTRACTED -> refresh when the verdict lands.
 */
export default function ProcessingPoller({
  id,
  waitForRecord = false,
}: {
  id: string;
  waitForRecord?: boolean;
}) {
  const router = useRouter();

  useEffect(() => {
    const timer = setInterval(async () => {
      if (document.visibilityState === "hidden") return;
      try {
        const decl = await getDeclaration(id);
        if (waitForRecord ? decl !== null : decl && decl.status !== "EXTRACTED") {
          router.refresh();
        }
      } catch {
        /* transient */
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [id, waitForRecord, router]);

  return (
    <div className="card">
      <div className="processing">
        <span className="spinner" />
        <div>
          <p style={{ margin: 0, fontWeight: 600 }}>
            {waitForRecord ? "Se extrage documentul" : "Se procesează"}
          </p>
          <p className="muted" style={{ margin: 0 }}>
            {waitForRecord
              ? "Documentul a fost încărcat; extracția pornește în câteva secunde."
              : "Verificările rulează. Pagina se actualizează singură."}
          </p>
        </div>
      </div>
    </div>
  );
}
