"use client";
import { Suspense, use, useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowSquareOut, ArrowClockwise, CheckCircle } from "@phosphor-icons/react";
import { api, ApiError } from "@/lib/api";
import { Card, Reveal, SectionHead, Skeleton, StatusBadge, btnPrimary } from "@/components/ui";

type Inv = {
  id: number; paypal_invoice_id: string; invoice_number: string; amount: number;
  currency: string; status: string; hosted_url: string; live_status: string | null;
  warning: string | null;
  payments: { paypal_payment_id: string; amount: number; currency: string; verified_via: string; received_at: string }[];
  timeline: { kind: string; message: string; at: string }[];
};

export default function InvoicePage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<p className="text-slate-500">Loading…</p>}>
      <Body params={params} />
    </Suspense>
  );
}

function Body({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [inv, setInv] = useState<Inv | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setInv((await api(`/api/invoices/${id}`)) as Inv);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Load failed.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function refresh() {
    setBusy(true);
    setErr("");
    try {
      await api(`/api/invoices/${id}/refresh`, { method: "POST" });
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Refresh failed.");
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (!inv && !err)
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-56" />
      </div>
    );
  if (!inv) return <Card className="p-6 text-sm text-red-600">{err}</Card>;

  return (
    <div className="space-y-5">
      <Reveal>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-3xl font-bold tracking-tight text-navy-950">
            Invoice #{inv.invoice_number || inv.id}
          </h1>
          <StatusBadge status={inv.status} />
        </div>
      </Reveal>

      <Reveal delay={0.05}>
        <div className="bg-navy-950 text-white rounded-2xl overflow-hidden">
          <div className="px-6 sm:px-8 py-5 border-b border-white/10 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gold-500">Amount due</p>
              <p className="text-3xl font-bold tracking-tight mt-1">
                {inv.amount.toFixed(2)} <span className="text-base text-white/60">{inv.currency}</span>
              </p>
            </div>
            <div className="flex gap-2">
              {inv.hosted_url && (
                <a href={inv.hosted_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-5 py-2 rounded-full bg-gold-500 text-navy-950 text-sm font-semibold hover:bg-gold-600 active:scale-[0.98] transition">
                  Pay on PayPal <ArrowSquareOut size={16} />
                </a>
              )}
              <button onClick={refresh} disabled={busy} className="inline-flex items-center gap-1.5 px-5 py-2 rounded-full border border-white/25 text-sm font-semibold text-white hover:bg-white/10 active:scale-[0.98] transition disabled:opacity-50">
                <ArrowClockwise size={16} /> {busy ? "Checking…" : "Refresh"}
              </button>
            </div>
          </div>
          <dl className="px-6 sm:px-8 py-4 text-sm space-y-2">
            <div className="flex gap-3">
              <dt className="w-36 shrink-0 text-white/50 text-xs font-semibold uppercase tracking-wider pt-0.5">PayPal ID</dt>
              <dd className="font-mono text-xs break-all">{inv.paypal_invoice_id}</dd>
            </div>
            {inv.warning && <p className="text-amber-300 text-sm">{inv.warning}</p>}
            {err && <p className="text-red-300 text-sm">{err}</p>}
          </dl>
        </div>
      </Reveal>

      <Reveal delay={0.08}>
        <Card className="p-5 sm:p-6">
          <SectionHead title="Verified payments" sub="Only genuine PayPal-verified payments appear here" />
          {inv.payments.length === 0 ? (
            <p className="text-sm text-slate-500">
              No verified payments yet. Pay on the hosted page above, then hit Refresh — the dashboard updates from PayPal, never from a mock.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {inv.payments.map((p, i) => (
                <motion.li
                  key={p.paypal_payment_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className="flex items-center justify-between gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2.5"
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <CheckCircle size={18} weight="fill" className="text-emerald-600 shrink-0" />
                    <span className="min-w-0">
                      <code className="font-mono text-xs block truncate">{p.paypal_payment_id}</code>
                      <span className="text-[11px] text-slate-500">verified via {p.verified_via}</span>
                    </span>
                  </span>
                  <span className="font-bold text-sm whitespace-nowrap text-navy-950">
                    {p.amount.toFixed(2)} {p.currency}
                  </span>
                </motion.li>
              ))}
            </ul>
          )}
        </Card>
      </Reveal>

      <Reveal delay={0.1}>
        <Card className="p-5 sm:p-6">
          <SectionHead title="Timeline" sub="Oldest first" />
          {inv.timeline.length === 0 ? (
            <p className="text-sm text-slate-500">No events yet.</p>
          ) : (
            <ol className="relative border-l-2 border-[#e7ddc9] ml-1.5 space-y-4">
              {inv.timeline.map((a, k) => (
                <li key={k} className="pl-4 relative">
                  <span className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-brand-600 ring-4 ring-cream-50" />
                  <p className="text-sm text-slate-700">{a.message}</p>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </Reveal>
    </div>
  );
}
