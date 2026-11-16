"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, label, pct } from "@/lib/api";

type Report = {
  batch: { id: string; title: string; total_count: number; shortlist_percent: number; final_percent: number; final_count: number };
  candidate: { id: string; filename: string; status: string; error_code: string|null; project_urls: string[]; initial_score: number|null; match_probability: number|null; mandatory_probability: number|null; mandatory_pass: number; stack_match: number; equivalent_match: number; project_score: number|null; final_score: number|null; final_rank: number|null; is_finalist: number; model_name: string|null; initial: any; external: any[]; shortlist_tier: string|null };
  navigation: { previous: string|null; next: string|null; position: number|null; total: number };
};

function decisionText(candidate: Report["candidate"], batch: Report["batch"]) {
  if (candidate.status === "failed") return { title: "Screening could not be completed", body: "Open the batch dashboard for the processing error. This is not a rejection based on the resume." };
  if (candidate.is_finalist) return { title: "Included in the final shortlist", body: `This candidate ranked within the final ${batch.final_percent}% after project review.` };
  if (candidate.status === "deep_failed") return { title: "Project check could not finish", body: `The public project check failed${candidate.error_code ? ` (${label(candidate.error_code)})` : ""}. The candidate remains in the final comparison using resume-stage evidence; review the links manually.` };
  if (candidate.status === "not_shortlisted") {
    if (!candidate.mandatory_pass) return { title: "Not selected for Stage 2", body: `The model estimated ${pct(candidate.mandatory_probability)} evidence for the job's core requirements, below the 50% screening threshold. This is a model estimate; check it against the job description.` };
    return { title: "Not selected for Stage 2", body: `The resume met the core-evidence threshold but ranked outside the top ${batch.shortlist_percent}% selected for project review.` };
  }
  if (candidate.status === "deep_completed") return { title: "Project check complete", body: `The public project links were checked. This candidate did not rank within the final ${batch.final_percent}% selected after project review.` };
  if (candidate.status === "project_checking") return { title: "Stage 2 project review in progress", body: "This resume was selected after Stage 1. Its linked projects are being checked now." };
  if (candidate.status === "deep_queued") return { title: "Selected for Stage 2", body: "This resume was selected after Stage 1 and is waiting for its linked project checks." };
  if (candidate.status === "screening") return { title: "Stage 1: Reviewing resume", body: "The resume text is being compared with the job description." };
  if (candidate.status === "queued") return { title: "Waiting in queue", body: "This resume is waiting for the Stage 1 comparison to start." };
  if (candidate.status === "screened") return { title: "Stage 1 complete", body: "The resume was assessed and the batch is being ranked." };
  return { title: label(candidate.status), body: "This resume is being processed. The report will update as screening progresses." };
}

function statusText(candidate: Report["candidate"]) {
  if (candidate.is_finalist) return `Final shortlist #${candidate.final_rank}`;
  if (["deep_queued", "project_checking"].includes(candidate.status) && candidate.error_code === "github_rate_limited") return "Waiting for GitHub quota to reset";
  const words: Record<string,string> = {
    queued: "Queued for Stage 1", screening: "Stage 1: Resume review in progress", screened: "Stage 1: Ranking candidates",
    not_shortlisted: "Not selected for Stage 2", deep_queued: "Selected for Stage 2; waiting",
    project_checking: "Stage 2: Project review in progress", deep_completed: "Stage 2: Project review complete",
    deep_failed: "Stage 2: Review needs manual follow-up", failed: "Resume could not be processed",
  };
  return words[candidate.status] || label(candidate.status);
}

function tierText(tier: string|null) {
  const words: Record<string,string> = {
    preferred_stack: "Experience with requested technologies",
    equivalent_stack: "Comparable experience in a different technology stack",
    other_eligible: "Relevant core-role evidence",
  };
  return tier ? words[tier] || label(tier) : "Not selected for Stage 2";
}

function groupProjectSources(sources: any[]) {
  const groups = new Map<string, { name: string; sources: any[] }>();
  for (const source of sources || []) {
    const key = source.project_group_key || source.repository || source.url;
    const existing = groups.get(key) || { name: source.project_name || source.repository || (source.source_type === "github_profile" ? "Unmatched GitHub profile" : "Project"), sources: [] as any[] };
    existing.sources.push(source);
    groups.set(key, existing);
  }
  return [...groups.values()];
}

export default function CandidatePage() {
  const params = useParams<{ batchId: string; candidateId: string }>();
  const [data, setData] = useState<Report|null>(null); const [error,setError] = useState("");
  useEffect(() => { api<Report>(`/api/batches/${params.batchId}/candidates/${params.candidateId}`).then(setData).catch((e) => setError(e.message)); }, [params.batchId,params.candidateId]);
  if (error) return <main className="shell"><div className="error">{error}</div></main>;
  if (!data) return <main className="shell"><p>Loading candidate report…</p></main>;
  const {candidate,batch,navigation}=data;
  const decision=decisionText(candidate,batch);
  const projectGroups=groupProjectSources(candidate.external || []);
  const base=`/batches/${batch.id}/candidates/`;
  return <main className="shell wide report-shell">
    <header className="topbar"><Link className="brand" href="/">Resume Screening</Link><Link className="backlink" href={`/batches/${batch.id}`}>← Batch results</Link></header>
    <div className="candidate-nav"><Link className={`button secondary compact ${navigation.previous ? "" : "disabled"}`} aria-disabled={!navigation.previous} href={navigation.previous ? `${base}${navigation.previous}` : "#"}>← Previous</Link><span>Candidate {navigation.position ?? "—"} of {navigation.total}</span><Link className={`button secondary compact ${navigation.next ? "" : "disabled"}`} aria-disabled={!navigation.next} href={navigation.next ? `${base}${navigation.next}` : "#"}>Next →</Link></div>
    <section className="report-heading"><div><p className="eyebrow">CANDIDATE REPORT · {batch.title}</p><h1>{candidate.filename}</h1><p>Status: <b>{statusText(candidate)}</b></p></div><span className={`report-status ${candidate.is_finalist ? "selected" : ""}`}>{tierText(candidate.shortlist_tier)}</span></section>

    <section className={`decision-card ${candidate.is_finalist ? "decision-good" : ""}`}><p className="eyebrow">WHY THIS RESULT</p><h2>{decision.title}</h2><p>{decision.body}</p><small>AI scores are evidence estimates, not a final hiring decision. Check the resume and project evidence before deciding.</small></section>

    <section className="score-grid">
      <article><span>Overall role fit</span><b>{candidate.initial_score?.toFixed(1) ?? "—"}<small> / 100</small></b></article>
      <article><span>Core requirements</span><b>{pct(candidate.mandatory_probability)}</b><small>50% model threshold to enter ranking</small></article>
      <article><span>Requested stack</span><b>{pct(candidate.stack_match)}</b><small>Exact technology overlap</small></article>
      <article><span>Transferable experience</span><b>{pct(candidate.equivalent_match)}</b><small>Comparable experience across stacks</small></article>
    </section>

    <section className="panel report-panel"><div className="report-section-title"><div><p className="eyebrow">STAGE ONE · {candidate.model_name || "SCREENING MODEL"}</p><h2>Resume evidence</h2></div><span className="score-chip">{pct(candidate.initial?.score_confidence)} confidence</span></div>
      {candidate.initial?.input_truncated && <div className="warning">Part of the resume or job description was shortened before analysis.</div>}
      <p className="report-copy">The model compares the resume with the job description, estimates whether the core role requirements are evidenced, and gives extra ranking weight to the requested stack. A different stack can still rank well when experience appears transferable.</p>
      <div className="evidence-list">{(candidate.initial?.criteria || []).map((item:any) => <article className="evidence-row" key={item.category}><div><b>{item.criterion}</b><span>{label(item.category)}</span></div><strong>{pct(item.probability)}</strong></article>)}</div>
      {candidate.initial?.review_probability >= 0.5 && <div className="review-note"><b>Review note:</b> The model marked this resume or the job requirements as unclear. Read the source resume before relying on the score.</div>}
    </section>

    <section className="panel report-panel"><div className="report-section-title"><div><p className="eyebrow">STAGE TWO · PUBLIC PROJECT CHECKS</p><h2>Projects mentioned in the resume</h2></div><span className="score-chip">{projectGroups.length} projects · {candidate.external?.length || 0} links</span></div>
      <p className="report-copy">Project checks run for candidates selected for Stage 2. Only direct GitHub repository links listed in the resume are checked. GitHub profile links are ignored; repositories found by browsing a profile are never treated as the candidate’s projects.</p>
      {projectGroups.length ? <div className="project-list">{projectGroups.map((project:any,index:number) => <article className="project-card" key={project.name + index}>
        <div className="project-card-title"><div><span className="project-number">PROJECT {index+1}</span><h3>{project.name}</h3></div><span>{project.sources.length} linked source{project.sources.length === 1 ? "" : "s"}</span></div>
        {project.sources.map((source:any,sourceIndex:number) => <div className="project-source" key={`${source.url}-${sourceIndex}`}>
        <div className="project-source-head"><a href={source.url} target="_blank" rel="noreferrer">{source.repository || source.url} ↗</a><span className={`health ${source.health || (source.reachable ? "reachable" : "unavailable")}`}>{label(source.health || (source.reachable ? "reachable" : "unavailable"))}</span></div>
        {source.link_match_status && <div className={`link-association ${source.link_match_status === "profile_repository_unmatched" ? "link-unmatched" : ""}`}><b>Resume-to-project link:</b> {source.link_match_status === "direct_repository_link" ? "The resume links directly to this repository." : source.link_match_status === "profile_repo_name_matched" ? "This repository name matched the project description near the GitHub profile link." : "This is the GitHub profile only; no repository was matched to the project description."}</div>}
        {source.project_identity_status && <div className={`link-association ${source.project_identity_status !== "confirmed" ? "link-unmatched" : ""}`}><b>Project identity:</b> {source.project_identity_status === "confirmed" ? "The linked public source corresponds to the resume project name or description. This does not verify authorship." : "Not confirmed from the available project name/description. This source was not used to increase or reduce the candidate's score."}</div>}
        {source.project_match_note && <p className="report-copy">{source.project_match_note}</p>}
        {sourceIndex === 0 && source.candidate_claim_excerpt && source.claim_scope !== "pdf_page" && <div className="claim-box"><b>Resume project summary</b><p>{source.candidate_claim_excerpt}</p></div>}
        {source.claim_comparison && source.project_identity_status === "confirmed" && source.claim_scope !== "pdf_page" && <div className="claim-check"><b>Resume description compared with public project text</b><p>{source.claim_comparison.matched_terms.length} of {source.claim_comparison.claim_terms.length} distinctive terms also appeared in the public material. This checks the linked project’s public text; it is a corroboration hint, not proof of authorship or feature behavior.</p>{source.claim_comparison.evidence?.length > 0 && <div className="match-terms">{source.claim_comparison.evidence.map((item:any)=><span key={item.term}>{item.term}</span>)}</div>}</div>}
        {source.claim_scope === "pdf_page" && <p className="project-meta">The resume link is embedded in a PDF. Its project description could not be tied to a specific text block on the page, so feature and technology claims from that page were not treated as verified.</p>}
        {source.manifest_files?.length > 0 && <p className="project-meta"><b>Project files checked:</b> {source.manifest_files.join(", ")}{source.source_files?.length ? `, ${source.source_files.length} source files sampled` : ""}</p>}
        {source.technologies?.length > 0 && <p className="project-meta"><b>Technologies found:</b> {source.technologies.join(", ")}</p>}
        {source.technology_checks?.length > 0 && <div className="technology-list"><b>Resume technology claims</b>{source.technology_checks.map((check:any) => <p className={check.status === "possible_mismatch" ? "review-flag" : ""} key={check.technology}><span>{check.technology}</span><span>{label(check.status)}</span></p>)}</div>}
        {source.checks && <details className="site-details"><summary>Website availability details</summary><p>HTTP {source.http_status || "—"} · page title {source.checks.html_title ? "found" : "missing"} · visible text {source.checks.visible_text ? "found" : "missing"} · This does not test buttons, forms, or logged-in features.</p></details>}
        {source.evidence?.length > 0 && <div className="public-evidence"><b>Role-related words found in public project material</b>{source.evidence.map((finding:any)=><p key={finding.criterion}>{finding.snippet}</p>)}</div>}
        </div>)}
      </article>)}</div> : candidate.project_urls?.length ? <div className="empty-projects"><b>{candidate.status === "not_shortlisted" ? "Project links found, checks not started" : ["deep_queued", "project_checking"].includes(candidate.status) ? "Project checks are in progress" : "No project check results saved"}</b><p>{candidate.status === "not_shortlisted" ? "Project checks run in stage two for candidates who advance from stage one. This resume did not advance, so its project links have not been checked." : "The resume contains these project URLs, but this batch has no completed check results for them yet."}</p><ul className="resume-link-list">{candidate.project_urls.map((url,index)=><li key={`${url}-${index}`}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul></div> : <div className="empty-projects"><b>No project links were found in the resume’s Projects section</b><p>Code-practice profiles and general contact links are excluded. Only project-linked GitHub repositories and hosted demos are checked.</p></div>}
      <div className="project-adjustment"><span>Project evidence adjustment</span><b>{candidate.project_score === null ? "Pending" : `${candidate.project_score > 0 ? "+" : ""}${candidate.project_score.toFixed(1)} points`}</b><small>Public evidence can support claims. A missing link or unverified claim is not proof it is false.</small></div>
    </section>
    <div className="bottom-nav"><Link className="button secondary compact" href={`/batches/${batch.id}`}>Back to batch</Link><span>{navigation.position ?? "—"} / {navigation.total}</span><Link className={`button secondary compact ${navigation.next ? "" : "disabled"}`} aria-disabled={!navigation.next} href={navigation.next ? `${base}${navigation.next}` : "#"}>Next candidate →</Link></div>
  </main>;
}
