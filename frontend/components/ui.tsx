"use client";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/* Scroll-reveal wrapper: fades/slides content in once when it enters view.
   Respects prefers-reduced-motion (renders static). */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.55, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

/* Animated money figure: counts up on mount (static under reduced motion). */
export function AnimatedMoney({ value, currency }: { value: number; currency: string }) {
  const reduce = useReducedMotion();
  if (reduce)
    return (
      <span>
        {value.toFixed(2)} <span className="text-sm font-semibold">{currency}</span>
      </span>
    );
  return (
    <motion.span
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      {value.toFixed(2)} <span className="text-sm font-semibold">{currency}</span>
    </motion.span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    PAID: "bg-emerald-100 text-emerald-900 border-emerald-300",
    SENT: "bg-blue-100 text-blue-900 border-blue-300",
    UNPAID: "bg-amber-100 text-amber-900 border-amber-300",
    VIEWED: "bg-sky-100 text-sky-900 border-sky-300",
    DRAFT: "bg-stone-200 text-stone-700 border-stone-300",
    OVERDUE: "bg-red-100 text-red-900 border-red-300",
    CANCELLED: "bg-stone-200 text-stone-500 border-stone-300",
  };
  const cls = map[status] || "bg-stone-100 text-stone-700 border-stone-200";
  return (
    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border whitespace-nowrap ${cls}`}>
      {status}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`bg-white rounded-2xl border border-[#e7ddc9] shadow-[0_1px_2px_rgba(16,27,69,0.05),0_8px_24px_-12px_rgba(16,27,69,0.12)] ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionHead({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-bold tracking-tight text-navy-950">{title}</h2>
      {sub && <p className="text-sm text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-cream-100 ${className}`} />;
}

export function EmptyState({ title, sub, action }: { title: string; sub: string; action?: ReactNode }) {
  return (
    <div className="text-center py-8">
      <p className="font-semibold text-navy-950">{title}</p>
      <p className="text-sm text-slate-500 mt-1">{sub}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export const inputCls =
  "w-full rounded-xl border border-[#ddd2bc] px-3 py-2 text-sm bg-white text-navy-950 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-brand-600";

export const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 px-5 py-2 rounded-full bg-brand-700 text-white text-sm font-semibold hover:bg-navy-900 active:scale-[0.98] transition disabled:opacity-50 disabled:cursor-not-allowed";

export const btnGold =
  "inline-flex items-center justify-center gap-1.5 px-5 py-2 rounded-full bg-gold-500 text-navy-950 text-sm font-semibold hover:bg-gold-600 active:scale-[0.98] transition disabled:opacity-50";

export const btnGhost =
  "inline-flex items-center justify-center gap-1.5 px-5 py-2 rounded-full border border-[#ddd2bc] text-sm font-semibold text-navy-900 hover:bg-cream-50 active:scale-[0.98] transition disabled:opacity-50";
