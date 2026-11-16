"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { API_BASE, api, label } from "@/lib/api";

type BatchRow = { id: string; title: string; status: string; total_count: number; created_at: string };
type AppConfig = { provider: string; provider_ready: boolean };

function batchStatus(value: string) {
  if (value === "screening") return "Stage 1 screening";
  if (value === "deep_analysis") return "Project checks";
  if (value === "completed") return "Review finished";
  if (value === "failed") return "Needs attention";
  return label(value);
}

export default function Home() {
  const [batches, setBatches] = useState<BatchRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [config, setConfig] = useState<AppConfig>({provider:"laya",provider_ready:false});
  const [files, setFiles] = useState<File[]>([]);
  const [addedMessage, setAddedMessage] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<{ batches: BatchRow[] }>("/api/batches").then((data) => setBatches(data.batches)).catch(() => {});
    api<AppConfig>("/api/config").then(setConfig).catch(() => {});
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const form = new FormData(event.currentTarget);
    form.delete("resumes");
    files.forEach((file) => form.append("resumes", file));
    try {
      const response = await fetch(`${API_BASE}/api/batches`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not create the batch.");
      window.location.href = `/batches/${payload.batch_id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the batch."); setBusy(false);
    }
  }

  function addFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.currentTarget.files || []);
    if (selected.length) {
      setFiles((current) => [...current, ...selected]);
      setAddedMessage(`Added ${selected.length} resume${selected.length === 1 ? "" : "s"}. ${files.length + selected.length} selected in total.`);
    }
    event.currentTarget.value = "";
  }

  return <main className="shell">
    <header className="topbar"><Link className="brand" href="/">Resume Screening</Link><span className="pill">STUDENT PROJECT</span></header>
    <section className="hero"><p className="eyebrow">EVIDENCE-LED CANDIDATE REVIEW</p><h1>Review the work<br />behind the resume.</h1><p>Compare resumes to a role, check public project evidence, and keep a human reviewer in the loop.</p></section>
    {config.provider === "laya" ? <div className="warning"><strong>Experimental model:</strong> LAYA misranked a small fictional example during a smoke check. Review every result and do not use it as an automatic hiring decision.</div> : <div className="notice">Stage one uses TypeSafe Jev. Extracted resume text is sent to TypeSafe for analysis.</div>}
    {!config.provider_ready && <div className="error">Screening setup is incomplete. Check the root .env file and install project dependencies.</div>}
    {error && <div className="error">{error}</div>}
    <form className="panel form" onSubmit={submit}>
      <div className="section-head"><span>01</span><div><h2>Role details</h2><p>The screening model reads the job description and infers core requirements, preferred technologies, and transferable experience.</p></div></div>
      <label>Job title<input name="title" required maxLength={200} placeholder="Full Stack Engineer" /></label>
      <label>Job description<textarea name="job_description" required minLength={30} maxLength={30000} rows={6} placeholder="Paste the role responsibilities and requirements" /></label>
      <div className="section-head separated"><span>02</span><div><h2>Shortlist settings</h2><p>Choose what share advances to project review and what share of that group makes the final shortlist.</p></div></div>
      <div className="two-cols"><label>Advance to project review (%)<input name="shortlist_percent" type="number" min={1} max={100} defaultValue={30} required /></label><label>Final shortlist from stage one (%)<input name="final_percent" type="number" min={1} max={100} defaultValue={10} required /><small>Applied to the number that actually advances to project review.</small></label></div>
      <div className="section-head separated"><span>03</span><div><h2>Resumes</h2><p>PDF or DOCX · 15 MB each · up to 3,000 files.</p></div></div>
      <div className="filebox"><div className="filebox-head"><div><b>Resume files</b><small>Select several files at once, or add more in another selection.</small></div><button className="button secondary add-files" type="button" onClick={() => fileInput.current?.click()}>+ Add resumes</button><input ref={fileInput} className="hidden-file-input" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple onChange={addFiles} /></div>
        <div className="file-count" aria-live="polite">{files.length ? `${files.length} resume${files.length === 1 ? "" : "s"} selected` : "No resumes selected"}{addedMessage && <span className="added-message"> · {addedMessage}</span>}</div>
        {files.length > 0 && <ul className="file-list">{files.map((file,index) => <li key={`${file.name}:${file.size}:${file.lastModified}:${index}`}><span><b>{file.name}</b><small>{(file.size / (1024 * 1024)).toFixed(1)} MB</small></span><button type="button" aria-label={`Remove ${file.name}`} onClick={() => { setFiles((current) => current.filter((_,i) => i !== index)); setAddedMessage(""); }}>Remove</button></li>)}</ul>}
      </div>
      <label className="consent"><input name="consent" type="checkbox" value="true" required />I have permission to process these resumes. {config.provider === "laya" ? "LAYA inference runs locally; project-link checks access public websites and GitHub." : "Extracted resume text will be sent to Jev; project-link checks access public websites and GitHub."}</label>
      <button className="primary" disabled={busy || !config.provider_ready || files.length === 0}>{busy ? "Creating batch…" : "Create screening batch →"}</button>
      <p className="fine">Scanned PDFs are unsupported. LAYA downloads model weights the first time it runs. For evaluation, start with a few resumes.</p>
    </form>
    {batches.length > 0 && <section className="history"><div className="history-title"><h2>Recent batches</h2><span>{batches.length} shown</span></div>{batches.map((batch) => <Link className="history-row" key={batch.id} href={`/batches/${batch.id}`}><span><b>{batch.title}</b><small>{batch.total_count} resumes · {batchStatus(batch.status)}</small></span><span>→</span></Link>)}</section>}
    <footer>Next.js interface · FastAPI API · SQLite task queue · {config.provider.toUpperCase()} stage one</footer>
  </main>;
}
