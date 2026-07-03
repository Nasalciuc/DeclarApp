import { getDeclaration, getDocumentUrl } from "@/actions/declarations";
import ChecksPanel from "@/components/checks-panel";
import ProcessingPoller from "@/components/processing-poller";
import StatusStamp from "@/components/status-stamp";
import { fmtDate } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function DeclarationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const decl = await getDeclaration(id);

  // Right after upload the record doesn't exist yet (extract takes a few
  // seconds) - show the pending screen and poll instead of a 404.
  if (!decl) {
    return (
      <div>
        <div className="page-head">
          <div>
            <p className="eyebrow">declarație · caseta 7</p>
            <h1 className="mono">{id}</h1>
          </div>
          <StatusStamp status="EXTRACTED" />
        </div>
        <ProcessingPoller id={id} waitForRecord />
      </div>
    );
  }

  const docUrl = decl.s3_key ? await getDocumentUrl(decl.s3_key) : null;
  const importer = decl.extracted?.parti?.importator?.nume;
  const count = decl.extracted?.marfuri?.length ?? 0;
  const currency = decl.extracted?.financiar?.valuta ?? "MDL";

  return (
    <div>
      <div className="page-head">
        <div>
          <p className="eyebrow">declarație · caseta 7</p>
          <h1 className="mono">{decl.declaration_id}</h1>
          <p className="muted">
            {importer ? `${importer} · ` : ""}
            {fmtDate(decl.created_at)}
            {count ? ` · ${count} mărfuri` : ""}
          </p>
        </div>
        <StatusStamp status={decl.status} />
      </div>

      <div className="split">
        <aside className="card doc-card">
          <div className="doc-head">
            <span>Document</span>
            {docUrl && (
              <a href={docUrl} target="_blank" rel="noreferrer">
                deschide ↗
              </a>
            )}
          </div>
          {docUrl ? (
            <iframe className="doc-frame" src={docUrl} title="Declarație" />
          ) : (
            <div className="doc-frame" />
          )}
        </aside>

        <section>
          {decl.status === "EXTRACTED" && (
            <ProcessingPoller id={decl.declaration_id} />
          )}

          {decl.status === "ERROR" && (
            <div className="card">
              <p className="eyebrow" style={{ color: "var(--fail)" }}>
                eroare
              </p>
              <p>
                Extracția acestei declarații a eșuat. Poți reîncărca documentul.
              </p>
              {decl.error && <p className="muted mono">{decl.error}</p>}
            </div>
          )}

          {(decl.status === "VALIDATED" || decl.status === "FLAGGED") && (
            <ChecksPanel declaration={decl} currency={currency} />
          )}
        </section>
      </div>
    </div>
  );
}
