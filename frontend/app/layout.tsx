import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PaySarthi — Verified international payments",
  description: "From Hindi conversations to verified international payments.",
};

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/agreements/new", label: "New agreement" },
  { href: "/assistant", label: "AI assistant" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <div className="min-h-screen lg:flex">
          <aside className="bg-navy-950 text-white lg:w-64 lg:min-h-screen lg:sticky lg:top-0 shrink-0">
            <div className="px-6 pt-6 pb-5 border-b border-white/10">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gold-500 text-navy-950 font-bold text-lg">
                  P
                </span>
                <div>
                  <div className="text-lg font-bold tracking-tight leading-none">PaySarthi</div>
                  <div className="text-[11px] text-white/55 mt-1 leading-tight">
                    Hindi conversations → verified payments
                  </div>
                </div>
              </div>
              <span className="inline-block mt-3 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-amber-400/15 text-amber-300 border border-amber-300/30">
                SANDBOX · test money only
              </span>
            </div>
            <nav className="px-3 py-4 flex lg:flex-col gap-1 overflow-x-auto">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="px-3 py-2 rounded-xl text-sm font-medium text-white/75 hover:bg-white/10 hover:text-white active:scale-[0.98] transition whitespace-nowrap"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
            <div className="hidden lg:block px-6 py-4 mt-auto text-[11px] text-white/40">
              PayPal Sandbox + AI
            </div>
          </aside>
          <main className="flex-1 min-w-0">
            <div className="max-w-5xl mx-auto px-4 sm:px-8 py-8">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
