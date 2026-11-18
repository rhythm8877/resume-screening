"use client";

import { API_BASE, api, label } from "@/lib/api";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Brand, Icon, ProgressBar, StatusBadge } from "@/components/ui";

type Candidate = { id: string; filename: string; status: string; initial_score: number | null; match_probability: number | null; final_score: number | null; final_rank: number | null; is_finalist: number; shortlist_tier: string | null; error_code: string | null };
type Result = { batch: { id: string; title: string; status: string; total_count: number; shortlist_percent: number; final_percent: number; final_count: number; screening_provider: string; criteria: { name: string; category: string }[] }; counts: Record<string, number>; tasks: Record<string, number>; candidates: Candidate[]; finalists: Candidate[]; total: number };

function candidateStatus(candidate: Candidate) {
  const value = candidate.status;
  if (value === "deep_queued" && candidate.error_code === "github_rate_limited") return "Project links waiting to be checked";
  if (value === "queued" && candidate.error_code === "typesafe_rate_limited") return "Resume review waiting to restart";
  const words: Record<string, string> = {
    queued: "Waiting for resume review", screening: "Resume review in progress", screened: "Preparing candidate results",
    not_shortlisted: "Not moved to project review", deep_queued: "Waiting for project review", project_checking: "Project review in progress",
    deep_completed: "Project review complete", deep_failed: "Manual review needed", failed: "Could not process",
  };
  return words[value] || label(value);
}

function statusTone(candidate: Candidate) {
  if (candidate.is_finalist || candidate.status === "deep_completed") return "success" as const;
  if (["not_shortlisted", "failed", "deep_failed"].includes(candidate.status)) return "neutral" as const;
  return "active" as const;
}

function stageTwoOutcome(candidate: Candidate) {
  if (candidate.status === "not_shortlisted") return "Not moved to project review";
  if (candidate.status === "deep_queued") return candidate.error_code === "github_rate_limited" ? "Waiting for GitHub" : "Selected · waiting";
  if (candidate.status === "project_checking") return "Project checks running";
  if (candidate.status === "deep_completed") return "Checks complete";
  if (candidate.status === "deep_failed") return "Manual review needed";
  return "Not started";
}

function finalOutcome(candidate: Candidate) {
  if (candidate.is_finalist) return `Selected #${candidate.final_rank}`;
  if (["deep_completed", "deep_failed"].includes(candidate.status)) return "Not selected";
  if (candidate.status === "not_shortlisted") return "Not reviewed";
  return "Pending";
}

export default function BatchPage() {
  const params = useParams<{ batchId: string }>();
  const [data, setData] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const load = () => api<Result>(`/api/batches/${params.batchId}?page=${page}`).then((value) => { if (active) { setData(value); if (!["completed", "failed"].includes(value.batch.status)) timer = setTimeout(load, 3500); } }).catch((e) => { if (active) setError(e.message); });
    load(); return () => { active = false; clearTimeout(timer); };
  }, [params.batchId, page]);
  const shownCandidates = useMemo(() => {
    const rows = data?.candidates || [];
    return rows.filter((candidate) => {
      const matchesQuery = candidate.filename.toLowerCase().includes(query.trim().toLowerCase());
      return matchesQuery && (statusFilter === "all" || candidate.status === statusFilter);
    });
  }, [data, query, statusFilter]);

  if (error) return <main className="app-shell"><div className="workspace"><div className="alert alert-error">{error}</div><Link href="/dashboard" className="button button-outline">Back to dashboard</Link></div></main>;
  if (!data) return <main className="app-shell"><div className="workspace loading-state">Loading batch results…</div></main>;
  const { batch, counts, tasks, finalists } = data;
  const screened = (tasks.screening_completed || 0) + (tasks.screening_failed || 0);
  const projectChecked = (tasks.deep_completed || 0) + (tasks.deep_failed || 0);
  const advanced = (counts.deep_queued || 0) + (counts.project_checking || 0) + (counts.deep_completed || 0) + (counts.deep_failed || 0);
  const waiting = tasks.screening_queued || 0;
  const screeningNow = counts.screening || 0;
  const screeningProgress = batch.total_count ? Math.min(100, Math.round(screened / batch.total_count * 100)) : 0;
  const projectProgress = advanced ? Math.min(100, Math.round(projectChecked / advanced * 100)) : 0;
  const batchState = batch.status === "completed" ? "Completed" : batch.status === "failed" ? "Needs attention" : "Processing";

  return <main className="app-shell">
    <header className="app-header"><Brand /><div className="header-context"><span className={`header-dot ${batch.status === "completed" ? "dot-done" : ""}`} />{batchState}</div><Link href="/dashboard" className="header-action">＋ New batch</Link></header>
    <div className="workspace batch-workspace">
      <div className="breadcrumb"><Link href="/dashboard">Dashboard</Link><span>/</span><span>{batch.title}</span></div>
      <section className="batch-title-row"><div><p className="eyebrow">SCREENING BATCH</p><h1>{batch.title}</h1><p>{batch.total_count.toLocaleString()} resumes submitted</p></div><span className={`batch-state ${batch.status === "completed" ? "state-done" : ""}`}><i />{batchState}</span></section>
      {batch.screening_provider === "laya" && <div className="model-notice"><span>!</span><p><b>Automated scores are experimental.</b> Review each resume before making a decision.</p></div>}

      <section className="overview-card">
        <div className="overview-heading"><div><p className="eyebrow">BATCH OVERVIEW</p><h2>Screening progress</h2></div><span className="stage-caption">{batch.status === "completed" ? "All reviews complete" : "Updates automatically"}</span></div>
        <div className="progress-grid">
          <article className="progress-step"><div className="progress-step-top"><span className="step-index">01</span><span className="step-name">Resume review</span></div><b>{screened}<small> of {batch.total_count.toLocaleString()} reviewed</small></b><ProgressBar value={screeningProgress} label="Resume review completion" /><p>{waiting + screeningNow ? `${waiting + screeningNow} waiting or being reviewed` : "All resumes reviewed"}</p></article>
          <article className="progress-step"><div className="progress-step-top"><span className="step-index">02</span><span className="step-name">Project review</span></div><b>{projectChecked}<small> of {advanced} checked</small></b><ProgressBar value={projectProgress} label="Project review completion" /><p>{advanced} candidates moved on · up to {batch.shortlist_percent}%</p></article>
          <article className="progress-step progress-step-final"><div className="progress-step-top"><span className="step-index">03</span><span className="step-name">Final shortlist</span></div><b>{finalists.length}<small> of {batch.final_count} places</small></b><ProgressBar value={batch.final_count ? finalists.length / batch.final_count * 100 : 0} label="Final shortlist progress" /><p>Up to {batch.final_percent}% of candidates sent to project review</p></article>
        </div>
      </section>

      {finalists.length > 0 && <section className="finalists-card"><div className="overview-heading"><div><p className="eyebrow">SHORTLIST</p><h2>Final candidates <span className="count-badge">{finalists.length}</span></h2></div><p className="section-aside">Open a candidate to review their resume and projects</p></div><div className="finalist-list">{finalists.map((candidate) => <Link className="finalist-row" key={candidate.id} href={`/batches/${batch.id}/candidates/${candidate.id}`}><span className="rank-badge">{candidate.final_rank}</span><span className="finalist-name"><b>{candidate.filename}</b><small>Final review score</small></span><strong>{candidate.final_score?.toFixed(1) ?? "—"}<small> / 100</small></strong><span className="row-arrow">→</span></Link>)}</div></section>}

      <section className="candidate-section">
        <div className="candidate-section-heading"><div><p className="eyebrow">APPLICATIONS</p><h2>All candidates</h2><p>Overall fit is one ranking signal. Stage 1 also requires enough evidence for essential requirements.</p></div><a className="button button-outline export-button" href={`${API_BASE}/api/batches/${batch.id}/export.csv`}>↓ <span>Download list</span></a></div>
        <div className="selection-rule-note"><b>How Stage 1 advances candidates</b><span>Essential-requirements evidence must be at least 50%. Among eligible candidates, the system prioritizes evidence for named technologies, then related experience. The shortlist percentage sets the maximum number advanced.</span></div>
        <div className="results-toolbar"><label className="search-control"><Icon name="search" size={16} /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find by resume filename on this page" aria-label="Search resumes on this page" /></label><label className="filter-control"><span className="filter-label">Show</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter candidates by status"><option value="all">Everyone</option><option value="deep_completed">Project review complete</option><option value="deep_queued">Waiting for project review</option><option value="project_checking">Project review in progress</option><option value="not_shortlisted">Not moved to project review</option><option value="deep_failed">Needs manual review</option><option value="failed">Could not be reviewed</option></select></label></div>
        <div className="candidate-table-wrap"><table className="candidate-table"><thead><tr><th>Candidate</th><th>Overall fit</th><th>Current status</th><th>Project review</th><th>Shortlist</th><th aria-label="Open report" /></tr></thead><tbody>
          {shownCandidates.map((candidate) => <tr key={candidate.id}><td><Link className="candidate-name-link" href={`/batches/${batch.id}/candidates/${candidate.id}`}><span className="candidate-avatar">{candidate.filename.slice(0, 1).toUpperCase()}</span><span><b>{candidate.filename}</b><small>Resume report</small></span></Link></td><td><span className="fit-score">{candidate.initial_score?.toFixed(1) ?? "—"}<small> / 100</small></span></td><td><StatusBadge tone={statusTone(candidate)}>{candidateStatus(candidate)}</StatusBadge></td><td className="table-secondary">{stageTwoOutcome(candidate)}</td><td><span className={candidate.is_finalist ? "final-decision final-yes" : "final-decision"}>{finalOutcome(candidate)}</span></td><td><Link className="table-open" aria-label={`Open report for ${candidate.filename}`} href={`/batches/${batch.id}/candidates/${candidate.id}`}><Icon name="arrow-right" size={14} /></Link></td></tr>)}
          {shownCandidates.length === 0 && <tr><td className="no-results" colSpan={6}>No resumes match these filters on this page.</td></tr>}
        </tbody></table></div>
        <div className="table-footer"><span>Showing {data.candidates.length ? (page - 1) * 100 + 1 : 0}–{Math.min(page * 100, data.total)} of {data.total.toLocaleString()} resumes</span><div className="pagination"><button className="button button-small button-outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button><span>Page {page} of {Math.max(1, Math.ceil(data.total / 100))}</span><button className="button button-small button-outline" disabled={page >= Math.ceil(data.total / 100)} onClick={() => setPage(page + 1)}>Next →</button></div></div>
      </section>
      <p className="batch-footnote">Candidates may have relevant experience with different tools. Scores are estimates; review the resume and project links before making a decision.</p>
      <footer className="app-footer">Shortlist <span>·</span> Hiring team dashboard</footer>
    </div>
  </main>;
}
