"use client";
import { Suspense, use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { CheckCircle, PencilSimple } from "@phosphor-icons/react";
import { api, ApiError } from "@/lib/api";
import { Card, Field, Reveal, StatusBadge, inputCls, btnPrimary, btnGhost, btnGold } from "@/components/ui";

type Ag = {
  id: number; project_id: number; client_name: string; client_email: string;
  project_title: string; project_description: string; price: number; currency: string;
  deliverables: string[]; deadline: string; revision_limit: number;
  extra_work_terms: string; payment_terms: string; quotation_text: string; approved: boolean;
};

type Preview = {
  agreement_id: number; project_id: number; invoicer: string; recipient: string;
  detail: { currency_code: string; note: string; memo: string; payment_terms?: string };
  items: { name: string; description: string; quantity: string; unit_amount: { currency_code: string; value: string } }[];
  payment_terms: string;
  existing: { id: number; paypal_invoice_id: string; status: string; hosted_url: string } | null;
};

export default function Review({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<p className="text-slate-500">Loading…</p>}>
      <Body params={params} />
    </Suspense>
  );
}

function DocRow({ k, v }: { k: string; v: string }) {
  if (!v) return null;
  return (
    <div className="grid sm:grid-cols-[180px_1fr] gap-1 sm:gap-4 py-2.5 border-b border-[#f0e8d8] last:border-0">
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">{k}</dt>
      <dd className="text-sm text-navy-950 font-medium whitespace-pre-wrap">{v}</dd>
    </div>
  );
}

function Body({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [ag, setAg] = useState<Ag | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ id: number; paypal_invoice_id: string; status: string; hosted_url: string } | null>(null);
  const router = useRouter();

  async function load() {
    try {
      const a = (await api(`/api/agreements/${id}`)) as Ag;
      setAg(a);
      setEmail(a.client_email);
      setForm({
        client_name: a.client_name, client_email: a.client_email,
        project_title: a.project_title, project_description: a.project_description,
        price: String(a.price), currency: a.currency,
        deliverables: a.deliverables.join("\n"), deadline: a.deadline,
        revision_limit: String(a.revision_limit), extra_work_terms: a.extra_work_terms,
        payment_terms: a.payment_terms,
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function save() {
    setBusy(true);
    setErr("");
    try {
      const body: Record<string, unknown> = {
        ...form,
        price: Number(form.price),
        revision_limit: Number(form.revision_limit),
        deliverables: form.deliverables.split("\n").map((s) => s.trim()).filter(Boolean),
      };
      const r = (await api(`/api/agreements/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      })) as Ag;
      setAg(r);
      setEmail(r.client_email);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    setBusy(true);
    try {
      setAg((await api(`/api/agreements/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ approved: true }),
      })) as Ag);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Approval failed.");
    } finally {
      setBusy(false);
    }
  }

  async function prepare() {
    if (!ag) return;
    setErr("");
    try {
      const r = (await api("/api/invoices/prepare", {
        method: "POST",
        body: JSON.stringify({ agreement_id: ag.id, client_email: email || undefined }),
      })) as Preview;
      setPreview({ ...r, recipient: email || r.recipient });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Preview failed.");
    }
  }

  async function confirmSend() {
    if (!ag || !preview) return;
    if (!preview.recipient.includes("@")) {
      setErr("Client email is missing or invalid — the AI never invents it. Please type it above.");
      return;
    }
    setSending(true);
    setErr("");
    try {
      setResult((await api("/api/invoices/send", {
        method: "POST",
        body: JSON.stringify({ agreement_id: ag.id, client_email: preview.recipient }),
      })) as { id: number; paypal_invoice_id: string; status: string; hosted_url: string });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Invoice send failed.");
    } finally {
      setSending(false);
    }
  }

  if (err && !ag) return <Card className="p-6 text-sm text-red-600">{err}</Card>;
  if (!ag) return <p className="text-slate-500">Loading agreement…</p>;
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="space-y-5">
      <Reveal>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-3xl font-bold tracking-tight text-navy-950">Agreement #{ag.id}</h1>
          {ag.approved ? (
            <span className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-700">
              <CheckCircle size={18} weight="fill" /> Approved
            </span>
          ) : (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-900 border border-amber-300">
              AWAITING REVIEW
            </span>
          )}
        </div>
      </Reveal>

      <Reveal delay={0.05}>
        <div className="bg-navy-950 text-white rounded-2xl overflow-hidden">
          <div className="px-6 sm:px-8 py-5 border-b border-white/10 flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gold-500">Quotation</p>
              <p className="text-xl font-bold tracking-tight mt-1">{ag.project_title || "Untitled project"}</p>
            </div>
            <p className="text-right shrink-0">
              <span className="text-2xl font-bold text-gold-500">{ag.price.toFixed(2)}</span>
              <span className="text-sm text-white/60 ml-1">{ag.currency}</span>
            </p>
          </div>
          <dl className="px-6 sm:px-8 py-4 [&_dt]:!text-white/50 [&_dd]:!text-white [&_div]:!border-white/10">
            <DocRow k="Client" v={ag.client_name || "—"} />
            <DocRow k="Email" v={ag.client_email || "missing — edit to add"} />
            <DocRow k="Scope" v={ag.project_description} />
            <DocRow k="Deliverables" v={ag.deliverables.map((x) => `• ${x}`).join("\n")} />
            <DocRow k="Deadline" v={ag.deadline} />
            <DocRow k="Revisions" v={`${ag.revision_limit} included`} />
            <DocRow k="Extra work" v={ag.extra_work_terms} />
            <DocRow k="Payment terms" v={ag.payment_terms} />
          </dl>
        </div>
      </Reveal>

      {!editing ? (
        <Reveal delay={0.08}>
          <Card className="p-5 flex flex-wrap items-center gap-2">
            {!ag.approved && (
              <>
                <button className={btnGhost} onClick={() => setEditing(true)}>
                  <PencilSimple size={16} /> Edit fields
                </button>
                <button className={btnGold} disabled={busy} onClick={approve}>
                  <CheckCircle size={16} weight="fill" /> {busy ? "Approving…" : "Approve final agreement"}
                </button>
              </>
            )}
            {err && <p className="text-sm text-red-600 w-full">{err}</p>}
          </Card>
        </Reveal>
      ) : (
        <Card className="p-5 sm:p-6 space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Client name"><input className={inputCls} value={form.client_name} onChange={set("client_name")} /></Field>
            <Field label="Client email"><input className={inputCls} value={form.client_email} onChange={set("client_email")} /></Field>
            <Field label="Project title"><input className={inputCls} value={form.project_title} onChange={set("project_title")} /></Field>
            <Field label="Price"><input className={inputCls} type="number" step="0.01" min="0.01" value={form.price} onChange={set("price")} /></Field>
            <Field label="Currency"><input className={inputCls} value={form.currency} onChange={set("currency")} /></Field>
            <Field label="Deadline"><input className={inputCls} value={form.deadline} onChange={set("deadline")} /></Field>
            <Field label="Revision limit"><input className={inputCls} type="number" min="0" value={form.revision_limit} onChange={set("revision_limit")} /></Field>
          </div>
          <Field label="Project description"><textarea className={`${inputCls} min-h-20`} value={form.project_description} onChange={set("project_description")} /></Field>
          <Field label="Deliverables (one per line)"><textarea className={`${inputCls} min-h-20`} value={form.deliverables} onChange={set("deliverables")} /></Field>
          <Field label="Additional-work terms"><textarea className={inputCls} value={form.extra_work_terms} onChange={set("extra_work_terms")} /></Field>
          <Field label="Payment terms"><textarea className={inputCls} value={form.payment_terms} onChange={set("payment_terms")} /></Field>
          {err && <p className="text-sm text-red-600">{err}</p>}
          <div className="flex gap-2">
            <button className={btnPrimary} disabled={busy} onClick={save}>{busy ? "Saving…" : "Save changes"}</button>
            <button className={btnGhost} onClick={() => { setEditing(false); load(); }}>Cancel</button>
          </div>
        </Card>
      )}

      {ag.approved && !preview && !result && (
        <Reveal>
          <Card className="p-5 sm:p-6 space-y-3">
            <h2 className="font-bold text-navy-950">Stage A — invoice preview</h2>
            <Field label="Client email for this invoice">
              <input className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <button className={btnPrimary} onClick={prepare}>Prepare invoice preview</button>
          </Card>
        </Reveal>
      )}

      {preview && !result && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}>
          <Card className="overflow-hidden">
            <div className="bg-cream-100 border-b border-[#e7ddc9] px-5 sm:px-6 py-4 flex items-center justify-between flex-wrap gap-2">
              <h2 className="font-bold text-navy-950">Stage B — confirm & send</h2>
              <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-900 border border-amber-300">
                NOTHING SENT YET
              </span>
            </div>
            <div className="p-5 sm:p-6 space-y-4">
              <div className="grid sm:grid-cols-2 gap-4 text-sm">
                <div className="rounded-xl border border-[#e7ddc9] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">From (your sandbox business)</p>
                  <p className="font-medium text-navy-950 break-all mt-0.5">{preview.invoicer}</p>
                </div>
                <div className="rounded-xl border border-[#e7ddc9] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">To (client)</p>
                  <p className="font-medium text-navy-950 break-all mt-0.5">{preview.recipient}</p>
                </div>
              </div>
              <div className="rounded-xl overflow-hidden border border-[#e7ddc9]">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-navy-950 text-white text-left">
                      <th className="px-4 py-2.5 font-semibold">Item</th>
                      <th className="px-4 py-2.5 font-semibold w-16">Qty</th>
                      <th className="px-4 py-2.5 font-semibold text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#f0e8d8]">
                    {preview.items.map((it, k) => (
                      <tr key={k}>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-navy-950">{it.name}</p>
                          {it.description && <p className="text-xs text-slate-500 mt-0.5 line-clamp-3">{it.description}</p>}
                        </td>
                        <td className="px-4 py-3">{it.quantity}</td>
                        <td className="px-4 py-3 text-right font-bold text-navy-950 whitespace-nowrap">
                          {it.unit_amount.value} {it.unit_amount.currency_code}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(preview.detail?.note || preview.detail?.payment_terms || preview.payment_terms) && (
                <div className="text-sm space-y-1 bg-cream-50 border border-[#efe7d6] rounded-xl p-3">
                  {preview.detail?.note && <p><span className="text-slate-500">Note: </span>{preview.detail.note}</p>}
                  {(preview.detail?.payment_terms || preview.payment_terms) && (
                    <p><span className="text-slate-500">Payment terms on invoice: </span>{preview.detail?.payment_terms || preview.payment_terms}</p>
                  )}
                </div>
              )}
              {preview.existing && (
                <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                  An invoice already exists for this agreement ({preview.existing.paypal_invoice_id}, {preview.existing.status}) — sending will resume it, not duplicate it.
                </p>
              )}
              <Field label="Confirm recipient email">
                <input className={inputCls} value={preview.recipient} onChange={(e) => setPreview({ ...preview, recipient: e.target.value })} />
              </Field>
              {err && <p className="text-sm text-red-600">{err}</p>}
              <button className={btnGold} disabled={sending} onClick={confirmSend}>
                {sending ? "Sending via PayPal…" : "Confirm — send PayPal invoice"}
              </button>
            </div>
          </Card>
        </motion.div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
          <Card className="p-5 sm:p-6 space-y-2 border-emerald-300">
            <h2 className="font-bold text-emerald-800">Invoice sent via PayPal Sandbox</h2>
            <p className="text-sm">PayPal ID: <code className="font-mono text-xs bg-cream-50 px-1.5 py-0.5 rounded">{result.paypal_invoice_id}</code></p>
            <p className="text-sm flex gap-2 items-center">Status: <StatusBadge status={result.status} /></p>
            {result.hosted_url && (
              <a href={result.hosted_url} target="_blank" rel="noreferrer" className="text-sm text-brand-700 underline break-all font-medium">
                Open hosted PayPal payment page
              </a>
            )}
            <div className="flex gap-2 pt-1">
              <button className={btnGhost} onClick={() => router.push(`/invoices/${result.id}`)}>Track payment</button>
              <button className={btnGhost} onClick={() => router.push("/")}>Dashboard</button>
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
