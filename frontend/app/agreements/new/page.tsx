"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { ChatText, Sparkle } from "@phosphor-icons/react";
import { api, ApiError } from "@/lib/api";
import { Card, Field, Reveal, SectionHead, inputCls, btnPrimary } from "@/components/ui";

const EXAMPLE =
  "My US client wants a logo for $150. Delivery in 4 days. Two revisions included. Extra revisions are $10 each. Client email is client@example.com.";

const STEPS = ["Paste chat", "AI extracts", "You approve"];

export default function NewAgreement() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = (await api("/api/agreements", {
        method: "POST",
        body: JSON.stringify({ raw_text: text }),
      })) as { id: number };
      router.push(`/agreements/${r.id}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Extraction failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Reveal>
        <h1 className="text-3xl font-bold tracking-tight text-navy-950">Turn chat into a contract</h1>
        <p className="text-sm text-slate-500 mt-1">
          Paste the conversation in Hindi, Hinglish or English. AI structures it — you approve every word before anything is sent.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="grid grid-cols-3 gap-2">
          {STEPS.map((s, i) => (
            <div
              key={s}
              className={`rounded-xl border px-3 py-2.5 text-center text-xs font-semibold ${
                i === 0 ? "bg-navy-950 text-white border-navy-950" : "bg-white text-slate-500 border-[#e7ddc9]"
              }`}
            >
              <span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-gold-500 text-navy-950 text-[11px] font-bold">
                {i + 1}
              </span>
              {s}
            </div>
          ))}
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <Card className="p-5 sm:p-6">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Client conversation">
              <div className="relative">
                <ChatText size={18} className="absolute left-3 top-3 text-slate-400" />
                <textarea
                  className={`${inputCls} min-h-44 pl-9 leading-relaxed`}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={EXAMPLE}
                />
              </div>
            </Field>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <button type="button" className="text-xs font-semibold text-brand-700 hover:underline" onClick={() => setText(EXAMPLE)}>
                Fill an example
              </button>
              <span className="text-xs text-slate-400">{text.trim().length} characters</span>
            </div>
            {err && (
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2">
                {err}
              </motion.p>
            )}
            <button className={btnPrimary} disabled={busy || text.trim().length < 10}>
              <Sparkle size={16} weight="fill" />
              {busy ? "AI is reading your chat…" : "Extract agreement"}
            </button>
            {busy && (
              <div className="space-y-2" aria-hidden>
                <div className="animate-pulse rounded-lg bg-cream-100 h-4 w-3/4" />
                <div className="animate-pulse rounded-lg bg-cream-100 h-4 w-1/2" />
              </div>
            )}
          </form>
        </Card>
      </Reveal>
    </div>
  );
}
