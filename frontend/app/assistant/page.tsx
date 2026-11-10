"use client";
import { useRef, useState } from "react";
import { motion } from "motion/react";
import { PaperPlaneTilt, Robot } from "@phosphor-icons/react";
import { api, ApiError } from "@/lib/api";
import { Card, Field, Reveal, SectionHead, inputCls, btnPrimary, btnGhost } from "@/components/ui";

type Msg = { from: "you" | "ai"; text: string };

function Bubble({ m, i }: { m: Msg; i: number }) {
  const mine = m.from === "you";
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(i * 0.03, 0.3) }}
      className={`flex ${mine ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
          mine
            ? "bg-navy-950 text-white rounded-br-md"
            : "bg-white border border-[#e7ddc9] text-navy-950 rounded-bl-md shadow-sm"
        }`}
      >
        {m.text}
      </div>
    </motion.div>
  );
}

export default function Assistant() {
  const [q, setQ] = useState("");
  const [feed, setFeed] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [invId, setInvId] = useState("");
  const [draft, setDraft] = useState("");
  const [projId, setProjId] = useState("");
  const [req, setReq] = useState("");
  const [scope, setScope] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  function push(from: Msg["from"], text: string) {
    setFeed((f) => [...f, { from, text }]);
    setTimeout(() => bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }), 60);
  }

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim().length < 3 || busy) return;
    const question = q;
    setQ("");
    push("you", question);
    setBusy(true);
    setErr("");
    try {
      const r = (await api("/api/assistant/ask", {
        method: "POST",
        body: JSON.stringify({ question }),
      })) as { answer: string };
      push("ai", r.answer);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Assistant failed.");
    } finally {
      setBusy(false);
    }
  }

  async function reminder() {
    setErr("");
    setDraft("");
    try {
      const r = (await api("/api/assistant/reminder", {
        method: "POST",
        body: JSON.stringify({ invoice_id: Number(invId) }),
      })) as { draft: string };
      setDraft(r.draft);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Reminder failed.");
    }
  }

  async function scopeCheck() {
    setErr("");
    setScope("");
    try {
      const r = (await api("/api/assistant/scope-check", {
        method: "POST",
        body: JSON.stringify({ project_id: Number(projId), new_request: req }),
      })) as { in_scope: boolean; reason: string; suggested_extra_price: number; draft_reply: string };
      setScope(
        `${r.in_scope ? "IN SCOPE" : "OUT OF SCOPE"} — ${r.reason}` +
          (r.suggested_extra_price ? `\nSuggested extra price: ${r.suggested_extra_price}` : "") +
          (r.draft_reply ? `\n\nDraft reply:\n${r.draft_reply}` : "")
      );
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Scope check failed.");
    }
  }

  return (
    <div className="space-y-5">
      <Reveal>
        <h1 className="text-3xl font-bold tracking-tight text-navy-950">AI payment assistant</h1>
        <p className="text-sm text-slate-500 mt-1">Answers from your real invoices. Drafts only — nothing is ever sent automatically.</p>
      </Reveal>
      {err && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2">{err}</p>}

      <Reveal delay={0.05}>
        <div className="bg-navy-950 rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/10 flex items-center gap-2">
            <Robot size={20} weight="duotone" className="text-gold-500" />
            <span className="text-sm font-semibold text-white">Ask about your money</span>
          </div>
          <div className="px-4 sm:px-5 py-5 space-y-3 min-h-40 max-h-[420px] overflow-y-auto">
            {feed.length === 0 && (
              <p className="text-sm text-white/50 text-center py-6">
                Try “Which invoices are still unpaid?”
              </p>
            )}
            {feed.map((m, i) => (
              <Bubble key={i} m={m} i={i} />
            ))}
            {busy && (
              <div className="flex gap-1.5 px-1" aria-label="thinking">
                {[0, 1, 2].map((k) => (
                  <motion.span
                    key={k}
                    className="h-2 w-2 rounded-full bg-gold-500"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.1, repeat: Infinity, delay: k * 0.18 }}
                  />
                ))}
              </div>
            )}
            <div ref={bottom} />
          </div>
          <form onSubmit={ask} className="px-4 sm:px-5 pb-4 flex gap-2">
            <input
              className="flex-1 rounded-full bg-white/10 border border-white/15 px-4 py-2.5 text-sm text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-gold-500"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Ask about invoices & payments…"
            />
            <button className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-gold-500 text-navy-950 hover:bg-gold-600 active:scale-95 transition disabled:opacity-50" disabled={busy || q.trim().length < 3} aria-label="Send">
              <PaperPlaneTilt size={18} weight="fill" />
            </button>
          </form>
        </div>
      </Reveal>

      <div className="grid lg:grid-cols-2 gap-4">
        <Reveal>
          <Card className="p-5 space-y-3 h-full">
            <SectionHead title="Reminder draft" sub="Draft only — you send it yourself" />
            <div className="flex gap-2">
              <input className={inputCls} value={invId} onChange={(e) => setInvId(e.target.value)} placeholder="Invoice ID, e.g. 2" inputMode="numeric" />
              <button className={btnGhost} onClick={reminder}>Draft</button>
            </div>
            {draft && <p className="text-sm whitespace-pre-wrap bg-cream-50 border border-[#efe7d6] rounded-xl p-3">{draft}</p>}
          </Card>
        </Reveal>
        <Reveal delay={0.06}>
          <Card className="p-5 space-y-3 h-full">
            <SectionHead title="Scope check" sub="Is a new request extra work?" />
            <Field label="Project ID">
              <input className={inputCls} value={projId} onChange={(e) => setProjId(e.target.value)} placeholder="e.g. 2" inputMode="numeric" />
            </Field>
            <Field label="New client request">
              <textarea className={`${inputCls} min-h-20`} value={req} onChange={(e) => setReq(e.target.value)} placeholder="Client now also wants…" />
            </Field>
            <button className={btnPrimary} onClick={scopeCheck}>Analyze</button>
            {scope && <p className="text-sm whitespace-pre-wrap bg-cream-50 border border-[#efe7d6] rounded-xl p-3">{scope}</p>}
          </Card>
        </Reveal>
      </div>
    </div>
  );
}
