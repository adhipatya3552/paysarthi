"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { ArrowRight, CheckCircle, Clock, Wallet } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { AnimatedMoney, Card, EmptyState, Reveal, SectionHead, Skeleton, StatusBadge } from "@/components/ui";

type Dash = {
  totals_by_currency: Record<string, { invoiced: number; paid: number; pending: number }>;
  invoice_count: number;
  by_status: Record<string, number>;
  pending: { id: number; paypal_invoice_id: string; amount: number; currency: string; status: string }[];
  recent_payments: { paypal_payment_id: string; invoice_id: number; amount: number; currency: string; via: string }[];
  timeline: { kind: string; message: string; at: string }[];
  active_projects: number;
  environment: string;
};

const STAT_STYLE = [
  { icon: Wallet, tint: "bg-blue-100 text-blue-800" },
  { icon: CheckCircle, tint: "bg-emerald-100 text-emerald-800" },
  { icon: Clock, tint: "bg-amber-100 text-amber-800" },
];

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api("/api/dashboard")
      .then((r) => setD(r as Dash))
      .catch((e: Error) => setErr(e.message));
  }, []);

  if (err)
    return (
      <Card className="p-6">
        <p className="font-semibold text-navy-950">Couldn&apos;t load the dashboard</p>
        <p className="text-sm text-slate-600 mt-1">{err}</p>
        <p className="text-sm text-slate-600 mt-2">
          Is the backend running? Do you need to{" "}
          <Link href="/login" className="text-brand-700 underline font-medium">log in</Link>?
        </p>
      </Card>
    );
  if (!d)
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-56" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((k) => (
            <Skeleton key={k} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-48" />
      </div>
    );

  const totals = Object.entries(d.totals_by_currency);
  const cards = totals.flatMap(([cur, v]) => [
    { label: `${cur} INVOICED`, value: v.invoiced, cur, i: 0 },
    { label: `${cur} PAID`, value: v.paid, cur, i: 1 },
    { label: `${cur} PENDING`, value: v.pending, cur, i: 2 },
  ]);

  return (
    <div className="space-y-6">
      <Reveal>
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-navy-950">Your money, verified</h1>
            <p className="text-sm text-slate-500 mt-1">
              Every figure below comes from PayPal Sandbox — nothing simulated.
            </p>
          </div>
          <Link href="/agreements/new" className="inline-flex items-center gap-1.5 px-5 py-2 rounded-full bg-brand-700 text-white text-sm font-semibold hover:bg-navy-900 active:scale-[0.98] transition">
            New agreement <ArrowRight size={16} weight="bold" />
          </Link>
        </div>
      </Reveal>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.slice(0, 3).map((c, k) => {
          const S = STAT_STYLE[c.i];
          const Icon = S.icon;
          return (
            <Reveal key={c.label} delay={k * 0.07} className="h-full">
              <Card className="p-5 h-full">
                <div className="flex items-center gap-2">
                  <span className={`p-1.5 rounded-lg ${S.tint}`}>
                    <Icon size={18} weight="duotone" />
                  </span>
                  <span className="text-xs font-semibold text-slate-500">{c.label}</span>
                </div>
                <div className="text-[28px] font-bold tracking-tight text-navy-950 mt-2">
                  <AnimatedMoney value={c.value} currency={c.cur} />
                </div>
              </Card>
            </Reveal>
          );
        })}
        <div className="rounded-2xl p-5 bg-navy-950 border border-navy-950 shadow-[0_1px_2px_rgba(16,27,69,0.05),0_8px_24px_-12px_rgba(16,27,69,0.12)] text-white">
          <span className="text-xs font-semibold text-white/60">ACTIVE PROJECTS</span>
          <div className="text-[28px] font-bold mt-2">{d.active_projects}</div>
          <div className="text-sm text-white/60 mt-1">{d.invoice_count} invoices total</div>
        </div>
      </div>

      <Reveal>
        <Card className="p-5 sm:p-6">
          <SectionHead title="Pending invoices" sub="Needs your client's click on PayPal" />
          {d.pending.length === 0 ? (
            <EmptyState title="Nothing pending" sub="All caught up. New money will appear here." />
          ) : (
            <ul className="divide-y divide-[#efe7d6]">
              {d.pending.map((i) => (
                <li key={i.id}>
                  <Link href={`/invoices/${i.id}`} className="py-3 flex items-center justify-between gap-3 group">
                    <span className="text-sm font-semibold text-navy-950 group-hover:text-brand-700">
                      #{i.id} · {i.amount.toFixed(2)} {i.currency}
                    </span>
                    <StatusBadge status={i.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </Reveal>

      <div className="grid lg:grid-cols-2 gap-4">
        <Reveal>
          <Card className="p-5 sm:p-6 h-full">
            <SectionHead title="Verified payments" sub="PayPal-confirmed, with transaction IDs" />
            {d.recent_payments.length === 0 ? (
              <EmptyState title="No payments yet" sub="Verified payments land here automatically." />
            ) : (
              <motion.ul initial="hidden" animate="show" className="space-y-2.5">
                {d.recent_payments.map((p) => (
                  <motion.li
                    key={p.paypal_payment_id}
                    variants={{ hidden: { opacity: 0, x: -12 }, show: { opacity: 1, x: 0 } }}
                    className="flex items-center justify-between gap-3 bg-cream-50 border border-[#efe7d6] rounded-xl px-3 py-2.5"
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      <CheckCircle size={18} weight="fill" className="text-emerald-600 shrink-0" />
                      <code className="font-mono text-xs truncate">{p.paypal_payment_id}</code>
                    </span>
                    <span className="font-bold text-sm whitespace-nowrap text-navy-950">
                      {p.amount.toFixed(2)} {p.currency}
                    </span>
                  </motion.li>
                ))}
              </motion.ul>
            )}
          </Card>
        </Reveal>
        <Reveal delay={0.08}>
          <Card className="p-5 sm:p-6 h-full">
            <SectionHead title="Activity" sub="Latest first" />
            {d.timeline.length === 0 ? (
              <EmptyState title="Quiet so far" sub="Agreement and invoice events appear here." />
            ) : (
              <ol className="relative border-l-2 border-[#e7ddc9] ml-1.5 space-y-4">
                {d.timeline.map((a, k) => (
                  <li key={k} className="pl-4 relative">
                    <span className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-gold-500 ring-4 ring-cream-50" />
                    <p className="text-sm text-slate-700">{a.message}</p>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </Reveal>
      </div>
    </div>
  );
}
