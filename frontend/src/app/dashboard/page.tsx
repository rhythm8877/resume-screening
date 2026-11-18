"use client";

import { API_BASE, api, label } from "@/lib/api";
import Link from "next/link";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { Brand, Icon } from "@/components/ui";

type BatchRow = { id: string; title: string; status: string; total_count: number; created_at: string };
type AppConfig = { provider: string; provider_ready: boolean };

function batchStatus(value: string) {
  if (value === "screening") return "Resume review in progress";
  if (value === "deep_analysis") return "Project review in progress";
  if (value === "completed") return "Completed";
  if (value === "failed") return "Needs attention";
  return label(value);
}

export default function Home() {
  const [batches, setBatches] = useState<BatchRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [config, setConfig] = useState<AppConfig>({ provider: "laya", provider_ready: false });
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
      setAddedMessage(`${selected.length} resume${selected.length === 1 ? "" : "s"} added.`);
    }
    event.currentTarget.value = "";
  }

  return <main className="app-shell">
    <header className="app-header">
      <Brand />
      <div className="header-context"><span className="header-dot" /> Hiring workspace</div>
      <nav className="dashboard-header-links" aria-label="Dashboard navigation"><Link href="/">Homepage</Link></nav>
    </header>

    <div className="workspace home-workspace">
      <section className="page-intro">
        <div><p className="eyebrow">DASHBOARD <span>/</span> NEW BATCH</p><h1>Start a resume review</h1><p>Compare applications with the job requirements, then review candidate projects.</p></div>
      </section>

      {config.provider === "laya" && <div className="model-notice"><span>!</span><p><b>Automated scores are experimental.</b> Review each resume before making a decision.</p></div>}
      {!config.provider_ready && <div className="alert alert-error"><span className="alert-icon">!</span><p>Screening is not configured. Check the project setup before creating a batch.</p></div>}
      {error && <div className="alert alert-error"><span className="alert-icon">!</span><p>{error}</p></div>}

      <div className="home-grid">
        <form className="form-card" onSubmit={submit}>
            <div className="form-card-head"><div><p className="eyebrow">NEW BATCH</p><h2>Set up a role</h2></div><span className="required-note">Required fields</span></div>

          <section className="form-section">
            <div className="form-section-title"><span className="step-number">1</span><div><h3>Role details</h3><p>Paste the job description so candidate experience can be compared with the role.</p></div></div>
            <label className="field-label">Job title<input name="title" required maxLength={200} placeholder="e.g. Full Stack Engineer" /></label>
            <label className="field-label">Job description<textarea name="job_description" required minLength={30} maxLength={30000} rows={7} placeholder="Paste responsibilities, requirements, and any other role details…" /></label>
          </section>

          <section className="form-section">
            <div className="form-section-title"><span className="step-number">2</span><div><h3>Add resumes</h3><p>Upload PDF or DOCX files. You can add more files before creating the batch.</p></div></div>
            <div className="upload-box">
              <div className="upload-copy"><span className="upload-icon"><Icon name="upload" size={17} /></span><div><b>Upload candidate resumes</b><small>PDF or DOCX · up to 15 MB each · maximum 3,000 files</small></div></div>
              <button className="button button-outline" type="button" onClick={() => fileInput.current?.click()}>Choose files</button>
              <input ref={fileInput} className="visually-hidden" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple onChange={addFiles} />
            </div>
            <div className="upload-count" aria-live="polite"><b>{files.length ? `${files.length} resume${files.length === 1 ? "" : "s"} selected` : "No resumes added yet"}</b>{addedMessage && <span>{addedMessage}</span>}</div>
            {files.length > 0 && <ul className="file-list">{files.map((file, index) => <li key={`${file.name}:${file.size}:${file.lastModified}:${index}`}><span className="file-type">{file.name.toLowerCase().endsWith(".docx") ? "DOCX" : "PDF"}</span><span className="file-name"><b>{file.name}</b><small>{(file.size / (1024 * 1024)).toFixed(1)} MB</small></span><button className="remove-file" type="button" aria-label={`Remove ${file.name}`} onClick={() => { setFiles((current) => current.filter((_, i) => i !== index)); setAddedMessage(""); }}>Remove</button></li>)}</ul>}
          </section>

          <section className="form-section form-section-last">
            <div className="form-section-title"><span className="step-number">3</span><div><h3>Choose shortlist sizes</h3><p>These percentages set the maximum candidate group at each stage.</p></div></div>
            <div className="settings-grid">
              <label className="field-label">Advance to project review<div className="input-suffix"><input name="shortlist_percent" type="number" min={1} max={100} defaultValue={30} required /><span>%</span></div><small>Maximum share of resumes to receive project checks</small></label>
              <label className="field-label">Final shortlist<div className="input-suffix"><input name="final_percent" type="number" min={1} max={100} defaultValue={10} required /><span>%</span></div><small>Share of candidates selected for project review</small></label>
            </div>
          </section>

          <div className="form-footer">
            <label className="consent"><input name="consent" type="checkbox" value="true" required /><span>I have permission to process these resumes. {config.provider === "laya" ? "Resume analysis runs on this computer. Project links are checked online." : "Resume text is sent to Jev for analysis. Project links are checked online."}</span></label>
            <button className="button button-primary submit-button" disabled={busy || !config.provider_ready || files.length === 0}>{busy ? "Creating batch…" : "Create screening batch"}<span aria-hidden="true">→</span></button>
            <p className="form-note">Scanned PDFs cannot be read. Start with a small batch to review the results.</p>
          </div>
        </form>

        <aside className="sidebar-column">
          <section className="side-card flow-card"><div className="side-card-heading"><h2>What happens next</h2><span className="side-step-count">3 steps</span></div>
            <ol className="flow-list"><li><span className="flow-step">01</span><div><b>Resume review</b><p>Compare applications with the job description.</p></div></li><li><span className="flow-step">02</span><div><b>Project review</b><p>Check the project links provided in each resume.</p></div></li><li><span className="flow-step">03</span><div><b>Your shortlist</b><p>Review results and decide who moves forward.</p></div></li></ol>
            <p className="side-note">Results are a guide. Hiring decisions stay with your team.</p>
          </section>
          {batches.length > 0 && <section className="side-card recent-card"><div className="side-card-heading"><h2>Recent batches</h2></div><div className="recent-list">{batches.slice(0, 5).map((batch) => <Link className="recent-item" key={batch.id} href={`/batches/${batch.id}`}><span className="recent-bullet" /><span className="recent-info"><b>{batch.title}</b><small>{batch.total_count} resumes</small></span><span className="recent-status">{batchStatus(batch.status)}</span><span className="recent-arrow">→</span></Link>)}</div></section>}
          <div className="privacy-note"><span><Icon name="check" size={12} /></span><p><b>Candidate information</b><small>Only upload resumes you are authorized to process.</small></p></div>
        </aside>
      </div>
      <footer className="app-footer">Shortlist <span>·</span> Hiring team dashboard</footer>
    </div>
  </main>;
}
