import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Vamal · Analizor declarații",
  description:
    "Extrage și verifică declarații vamale: format, fiscal, consistență, semantic.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ro" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <header className="site-header">
          <div className="shell header-row">
            <Link href="/" className="brand">
              Vamal<span>·</span>Analizor
            </Link>
            <nav className="nav">
              <Link href="/">Declarații</Link>
              <Link href="/upload" className="btn btn-primary">
                Încarcă declarație
              </Link>
            </nav>
          </div>
        </header>
        <main className="main shell">{children}</main>
        <footer className="foot">
          Pipeline: extracție → 4 verificări → raport · Fază 1
        </footer>
      </body>
    </html>
  );
}
