"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { API_BASE, api, label, pct } from "@/lib/api";

type Candidate = { id: string; filename: string; status: string; initial_score: number | null; match_probability: number | null; final_score: number | null; final_rank: number | null; is_finalist: number; shortlist_tier: string | null; error_code: string | null };
type Result = { batch: { id: string; title: string; status: string; total_count: number; shortlist_percent: number; final_percent: number; final_count: number; screening_provider: string; criteria: {name:string; category:string}[] }; counts: Record<string, number>; tasks: Record<string, number>; candidates: Candidate[]; finalists: Candidate[]; total: number };

function candidateStatus(candidate: Candidate) {
  const value = candidate.status;
  if (value === "deep_queued" && candidate.error_code === "github_rate_limited") return "Waiting for GitHub quota to reset";
  if (value === "queued" && candidate.error_code === "typesafe_rate_limited") return "Waiting for Jev quota to reset";
  const words: Record<string,string> = {
    queued: "Queued for Stage 1", screening: "Stage 1: Resume review in progress", screened: "Stage 1: Ranking candidates",
    not_shortlisted: "Not selected for Stage 2", deep_queued: "Selected for Stage 2; waiting",
    project_checking: "Stage 2: Project review in progress", deep_completed: "Stage 2: Project review complete",
    deep_failed: "Stage 2: Review needs manual follow-up", failed: "Resume could not be processed",
  };
  return words[value] || label(value);
}

function shortlistReason(value: string | null) {
  const words: Record<string,string> = {
    preferred_stack: "Resume shows experience with technologies requested in the job description.",
    equivalent_stack: "Resume shows comparable role experience using a different technology stack.",
    other_eligible: "Resume shows relevant core-role evidence; technology-stack evidence was limited.",
  };
  return value ? words[value] || label(value) : "Not selected for Stage 2";
}

function stageTwoOutcome(candidate: Candidate) {
  if (candidate.status === "not_shortlisted") return "Not selected for Stage 2";
  if (candidate.status === "deep_queued") return candidate.error_code === "github_rate_limited" ? "Waiting for GitHub quota reset" : "Selected; waiting to start";
  if (candidate.status === "project_checking") return "Project review in progress";
  if (candidate.status === "deep_completed") return "Project review complete";
  if (candidate.status === "deep_failed") return "Could not complete; manual review needed";
  return "Not started";
}

function finalOutcome(candidate: Candidate) {
  if (candidate.is_finalist) return `Selected #${candidate.final_rank}`;
  if (["deep_completed", "deep_failed"].includes(candidate.status)) return "Not selected";
  if (candidate.status === "not_shortlisted") return "Not reviewed in Stage 2";
  return "Pending";
}

export default function BatchPage() {
  const params = useParams<{ batchId: string }>();
  const [data, setData] = useState<Result | null>(null); const [error, setError] = useState(""); const [page,setPage]=useState(1);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const load = () => api<Result>(`/api/batches/${params.batchId}?page=${page}`).then((value) => { if (active) { setData(value); if (!["completed", "failed"].includes(value.batch.status)) timer = setTimeout(load, 3500); } }).catch((e) => { if (active) setError(e.message); });
    load(); return () => { active = false; clearTimeout(timer); };
  }, [params.batchId,page]);
  if (error) return <main className="shell"><div className="error">{error}</div><Link href="/">Back home</Link></main>;
  if (!data) return <main className="shell"><p>Loading batch…</p></main>;
  const { batch, counts, tasks, candidates, finalists } = data;
  const screened = (tasks.screening_completed || 0) + (tasks.screening_failed || 0);
  const projectChecked = (tasks.deep_completed || 0) + (tasks.deep_failed || 0);
  const advanced = (counts.deep_queued || 0) + (counts.project_checking || 0) + (counts.deep_completed || 0) + (counts.deep_failed || 0);
  const waiting = tasks.screening_queued || 0;
  const screeningNow = counts.screening || 0;
  return <main className="shell wide">
    <header className="topbar"><Link className="brand" href="/">Resume Screening</Link><Link href="/" className="backlink">New batch</Link></header>
    <section className="hero compact"><p className="eyebrow">BATCH DASHBOARD · {batch.status === "completed" ? "Review finished" : batch.status === "failed" ? "Needs attention" : "In progress"}</p><h1>{batch.title}</h1><p>{batch.total_count} resumes · up to {batch.shortlist_percent}% are selected for Stage 2 project review · {batch.final_percent}% of the Stage 2 group are selected for the final shortlist</p></section>
    {batch.screening_provider === "laya" && <div className="warning"><strong>Experimental LAYA rankings.</strong> This model has not been validated for resume screening. Review candidate evidence manually.</div>}
    <section className="pipeline panel"><h2>Screening progress</h2><div className="pipeline-grid">
      <article><span>1 · Uploaded</span><b>{batch.total_count}</b><small>resumes received</small></article>
      <article><span>2 · Queue and Stage 1</span><b>{waiting + screeningNow} waiting / active</b><small>{screened} of {batch.total_count} first-stage checks finished</small></article>
      <article><span>3 · Stage 1 decision</span><b>{advanced} selected for Stage 2</b><small>{counts.not_shortlisted || 0} not selected for project review</small></article>
      <article><span>4 · Stage 2 project review</span><b>{projectChecked} of {advanced} complete</b><small>{(counts.project_checking || 0) + (counts.deep_queued || 0)} waiting or in progress</small></article>
      <article><span>5 · Final shortlist</span><b>{finalists.length} of {advanced} selected</b><small>{batch.final_percent}% target · currently {batch.final_count} places</small></article>
    </div><p className="fine">Example: 3,000 resumes × 30% = up to 900 selected for Stage 2; 10% of that group = 90 final places. For a small group, the target rounds up to one if anyone is selected for Stage 2.</p></section>
    {finalists.length > 0 && <section className="panel"><h2>Final shortlist</h2><div className="final-grid">{finalists.map((candidate) => <Link className="final-item" key={candidate.id} href={`/batches/${batch.id}/candidates/${candidate.id}`}><b>#{candidate.final_rank}</b><span>{candidate.filename}</span><strong>{candidate.final_score?.toFixed(1)} pts</strong></Link>)}</div></section>}
    <section className="panel table-panel"><div className="panel-heading"><div><p className="eyebrow">ALL SUBMISSIONS</p><h2>Candidate progress</h2></div><a className="button" href={`${API_BASE}/api/batches/${batch.id}/export.csv`}>Download CSV</a></div>
      <div className="table-scroll"><table><thead><tr><th>Resume</th><th>Status</th><th>Core-role evidence</th><th>Role fit</th><th>Stage 1 selection reason</th><th>Stage 2 result</th><th>Final shortlist</th></tr></thead><tbody>
      {candidates.map((candidate) => <tr key={candidate.id}><td><Link href={`/batches/${batch.id}/candidates/${candidate.id}`}>{candidate.filename}</Link></td><td>{candidateStatus(candidate)}</td><td>{pct(candidate.match_probability)}</td><td>{candidate.initial_score?.toFixed(1) ?? "—"}</td><td>{shortlistReason(candidate.shortlist_tier)}</td><td>{stageTwoOutcome(candidate)}</td><td>{finalOutcome(candidate)}</td></tr>)}
      </tbody></table></div><div className="pagination"><button className="button secondary" disabled={page<=1} onClick={()=>setPage(page-1)}>← Previous</button><span>Page {page} of {Math.max(1,Math.ceil(data.total/100))} · {data.total} resumes</span><button className="button secondary" disabled={page>=Math.ceil(data.total/100)} onClick={()=>setPage(page+1)}>Next →</button></div><p className="fine">“Selected for Stage 2” means the resume ranked within the configured Stage 1 selection group. A different-stack match means relevant experience appears transferable to the role; it does not mean the technologies are identical. Final shortlist places are calculated from the Stage 2 group.</p>
    </section>
    <footer>Public evidence can support a claim, but missing evidence does not prove the resume is false.</footer>
  </main>;
}
