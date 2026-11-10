"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { LockKey } from "@phosphor-icons/react";
import { Card, Field, Reveal, inputCls, btnPrimary } from "@/components/ui";

export default function Login() {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${base}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    setBusy(false);
    if (!res.ok) {
      setErr("Wrong password. Try again.");
      return;
    }
    const data = await res.json();
    localStorage.setItem("ps_token", data.token);
    router.push("/");
  }

  return (
    <div className="max-w-md mx-auto pt-6">
      <Reveal>
        <div className="bg-navy-950 text-white rounded-2xl p-8 text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gold-500 text-navy-950 font-bold text-2xl">
            P
          </span>
          <h1 className="text-2xl font-bold tracking-tight mt-4">PaySarthi</h1>
          <p className="text-sm text-white/60 mt-1">
            From Hindi conversations to verified international payments.
          </p>
          <span className="inline-block mt-3 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-amber-400/15 text-amber-300 border border-amber-300/30">
            SANDBOX · test money only
          </span>
        </div>
      </Reveal>
      <Reveal delay={0.08}>
        <Card className="p-6 mt-4">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Demo password">
              <div className="relative">
                <LockKey size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="password"
                  className={`${inputCls} pl-9`}
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                  placeholder="Enter demo password"
                  autoComplete="current-password"
                />
              </div>
            </Field>
            {err && (
              <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="text-sm text-red-600">
                {err}
              </motion.p>
            )}
            <button className={`${btnPrimary} w-full`} type="submit" disabled={busy || !pw}>
              {busy ? "Checking…" : "Log in"}
            </button>
          </form>
        </Card>
      </Reveal>
    </div>
  );
}
