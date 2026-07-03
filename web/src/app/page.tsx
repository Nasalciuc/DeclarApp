import { listDeclarations } from "@/actions/declarations";
import DeclarationTable from "@/components/declaration-table";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const initial = await listDeclarations();
  return (
    <div>
      <p className="eyebrow">registru</p>
      <h1>Declarații</h1>
      <p className="lede">
        Fiecare declarație urcată e extrasă automat și trecută prin cele patru
        verificări. Cele marcate „de verificat" așteaptă un ochi uman.
      </p>
      <DeclarationTable initial={initial} />
    </div>
  );
}
