"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, label, pct } from "@/lib/api";
import { Brand, Icon } from "@/components/ui";

type Report = {
  batch: { id: string; title: string; total_count: number; shortlist_percent: number; final_percent: number; final_count: number };
  candidate: { id: string; filename: string; status: string; error_code: string|null; project_urls: string[]; initial_score: number|null; match_probability: number|null; mandatory_probability: number|null; mandatory_pass: number; stack_match: number; equivalent_match: number; project_score: number|null; final_score: number|null; final_rank: number|null; is_finalist: number; model_name: string|null; initial: any; external: any[]; shortlist_tier: string|null };
  navigation: { previous: string|null; next: string|null; position: number|null; total: number };
};

function decisionText(candidate: Report["candidate"], batch: Report["batch"]) {
  if (candidate.status === "failed") return { title: "Resume review could not be completed", body: "This is a processing issue, not a decision about the candidate. Check the batch status for details." };
  if (candidate.is_finalist) return { title: "Included in the final shortlist", body: `This candidate ranked within the final ${batch.final_percent}% after project review.` };
  if (candidate.status === "deep_failed") return { title: "Project check could not finish", body: "One or more public project links could not be checked. Review the links manually; this does not mean the resume is inaccurate." };
  if (candidate.status === "not_shortlisted") {
    if (!candidate.mandatory_pass) return { title: "Not selected for project review", body: `The resume contains limited information about the job's essential requirements (${pct(candidate.mandatory_probability)} estimate). Read the resume and job description before relying on this result.` };
    return { title: "Not selected for project review", body: `The resume met the initial requirements, but other candidates had a closer match. This batch advances up to ${batch.shortlist_percent}% of applicants to project review.` };
  }
  if (candidate.status === "deep_completed") return { title: "Project check complete", body: `The public project links were checked. This candidate did not rank within the final ${batch.final_percent}% selected after project review.` };
  if (candidate.status === "project_checking") return { title: "Project review in progress", body: "This candidate was selected for project review. The links in their resume are being checked." };
  if (candidate.status === "deep_queued") return { title: "Selected for project review", body: "This candidate is waiting for their project links to be checked." };
  if (candidate.status === "screening") return { title: "Resume review in progress", body: "The resume is being compared with the job description." };
  if (candidate.status === "queued") return { title: "Waiting for resume review", body: "This resume is waiting for its comparison with the job description." };
  if (candidate.status === "screened") return { title: "Resume review complete", body: "The resume was reviewed and candidates are being ranked." };
  return { title: label(candidate.status), body: "This resume is being processed. The report will update as screening progresses." };
}

function statusText(candidate: Report["candidate"]) {
  if (candidate.is_finalist) return `Final shortlist #${candidate.final_rank}`;
  if (["deep_queued", "project_checking"].includes(candidate.status) && candidate.error_code === "github_rate_limited") return "Project link checks are waiting";
  const words: Record<string,string> = {
    queued: "Waiting for resume review", screening: "Resume review in progress", screened: "Preparing candidate results",
    not_shortlisted: "Not moved to project review", deep_queued: "Selected for project review; waiting",
    project_checking: "Project review in progress", deep_completed: "Project review complete",
    deep_failed: "Project review needs a manual check", failed: "Resume could not be reviewed",
  };
  return words[candidate.status] || label(candidate.status);
}

function tierText(tier: string|null) {
  const words: Record<string,string> = {
    preferred_stack: "Experience with skills in the job description",
    equivalent_stack: "Related experience using different tools",
    other_eligible: "Relevant experience for the role",
  };
  return tier ? words[tier] || label(tier) : "Not selected for project review";
}

function categoryText(value: string) {
  const key = value.toLowerCase().replace(/[ -]+/g, "_");
  const words: Record<string, string> = {
    mandatory: "Essential requirement", required: "Essential requirement", core: "Essential requirement", required_skill: "Essential skill",
    preferred: "Preferred skill", preferred_skill: "Preferred skill", preferred_stack: "Skills named in the job description",
    equivalent: "Related experience", equivalent_stack: "Related experience", transferable: "Related experience", transferable_technology: "Related experience",
  };
  return words[key] || label(value);
}

function checkText(value: string) {
  const key = value.toLowerCase();
  const words: Record<string, string> = {
    found_in_source_code: "Seen in project code", declared_in_dependency_file: "Listed in project setup files",
    mentioned_in_readme: "Mentioned in project description", possible_mismatch: "Not found in checked files",
  };
  return words[key] || label(value);
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
  if (error) return <main className="app-shell"><div className="workspace"><div className="alert alert-error">{error}</div></div></main>;
  if (!data) return <main className="app-shell"><div className="workspace loading-state">Loading candidate report…</div></main>;
  const {candidate,batch,navigation}=data;
  const decision=decisionText(candidate,batch);
  const projectGroups=groupProjectSources(candidate.external || []);
  const base=`/batches/${batch.id}/candidates/`;
  return <main className="app-shell">
    <header className="app-header"><Brand /><div className="header-context"><span className="header-dot" />Candidate review</div><Link href={`/batches/${batch.id}`} className="header-action">← Batch results</Link></header>
    <div className="workspace report-workspace">
    <div className="candidate-nav"><Link className={`button button-small button-outline ${navigation.previous ? "" : "is-disabled"}`} aria-disabled={!navigation.previous} href={navigation.previous ? `${base}${navigation.previous}` : "#"}>← Previous</Link><span>Candidate {navigation.position ?? "—"} of {navigation.total}</span><Link className={`button button-small button-outline ${navigation.next ? "" : "is-disabled"}`} aria-disabled={!navigation.next} href={navigation.next ? `${base}${navigation.next}` : "#"}>Next <Icon name="arrow-right" size={13} /></Link></div>
    <section className="report-heading"><div><p className="eyebrow">{batch.title} <span>/</span> CANDIDATE REPORT</p><h1>{candidate.filename}</h1><p className="candidate-current-status"><span className="header-dot" />{statusText(candidate)}</p></div><span className={`report-status ${candidate.is_finalist ? "selected" : ""}`}>{tierText(candidate.shortlist_tier)}</span></section>

    <section className={`decision-card ${candidate.is_finalist ? "decision-good" : ""}`}><div className="decision-icon"><Icon name={candidate.is_finalist ? "check" : "document"} size={16} /></div><div><p className="eyebrow">RESULT</p><h2>{decision.title}</h2><p>{decision.body}</p><small>Scores are estimates. Review the resume and project details before making a decision.</small></div></section>

    <section className="score-grid">
      <article><span>Overall fit estimate</span><b>{candidate.initial_score?.toFixed(1) ?? "—"}<small> / 100</small></b><small>One ranking signal; not a Stage 1 pass mark</small></article>
      <article><span>Essential requirements</span><b>{pct(candidate.mandatory_probability)}</b><small>At least 50% is needed to be eligible for Stage 2</small></article>
      <article><span>Skills named in the job</span><b>{pct(candidate.stack_match)}</b><small>Prioritized among eligible candidates</small></article>
      <article><span>Related experience</span><b>{pct(candidate.equivalent_match)}</b><small>Considered after named-stack evidence</small></article>
    </section>
    <div className="selection-rule-note report-rule-note"><b>How Stage 1 works</b><span>The essential-requirements estimate is the eligibility gate. The shortlist percentage limits how many eligible candidates advance. Technology fit and related experience affect the order; overall fit is considered within that ranking.</span></div>

    <section className="panel report-panel"><div className="report-section-title"><div><p className="eyebrow">RESUME REVIEW</p><h2>Job requirements</h2></div></div>
      {candidate.initial?.input_truncated && <div className="warning">Part of the resume or job description was shortened before analysis.</div>}
      <p className="report-copy">These estimates show how closely the resume supports the job requirements. A candidate may still be a good fit when they have relevant experience with different tools.</p>
      <div className="evidence-list">{(candidate.initial?.criteria || []).map((item:any,index:number) => <article className="evidence-row" key={`${item.criterion}-${index}`}><div><b>{item.criterion}</b><span>{categoryText(item.category)}</span></div><strong>{pct(item.probability)}</strong></article>)}</div>
      {candidate.initial?.review_probability >= 0.5 && <div className="review-note"><b>Needs a closer look:</b> The resume or job description was unclear to the screening system. Read the original resume before relying on these scores.</div>}
    </section>

    <section className="panel report-panel"><div className="report-section-title"><div><p className="eyebrow">PROJECT REVIEW</p><h2>Projects mentioned in the resume</h2></div><span className="score-chip">{projectGroups.length} projects · {candidate.external?.length || 0} links</span></div>
      <p className="report-copy">Only project links written in the resume are checked. A GitHub link must point to the specific project repository; a general profile link is not treated as proof of a project.</p>
      {projectGroups.length ? <div className="project-list">{projectGroups.map((project:any,index:number) => <article className="project-card" key={project.name + index}>
        <div className="project-card-title"><div><span className="project-number">PROJECT {index+1}</span><h3>{project.name}</h3></div><span>{project.sources.length} linked source{project.sources.length === 1 ? "" : "s"}</span></div>
        {project.sources.map((source:any,sourceIndex:number) => <div className="project-source" key={`${source.url}-${sourceIndex}`}>
        <div className="project-source-head"><a href={source.url} target="_blank" rel="noreferrer">{source.repository || source.url} ↗</a><span className={`health ${source.health || (source.reachable ? "reachable" : "unavailable")}`}>{label(source.health || (source.reachable ? "reachable" : "unavailable"))}</span></div>
        {source.link_match_status && <div className={`link-association ${source.link_match_status === "profile_repository_unmatched" ? "link-unmatched" : ""}`}><b>Resume-to-project link:</b> {source.link_match_status === "direct_repository_link" ? "The resume links directly to this repository." : source.link_match_status === "profile_repo_name_matched" ? "This repository name matched the project description near the GitHub profile link." : "This is the GitHub profile only; no repository was matched to the project description."}</div>}
        {source.project_identity_status && <div className={`link-association ${source.project_identity_status !== "confirmed" ? "link-unmatched" : ""}`}><b>Does the link match the project?</b> {source.project_identity_status === "confirmed" ? "The public page matches the project name or description in the resume. This does not confirm who built it." : "The match could not be confirmed from the available details. It did not change the candidate's score."}</div>}
        {source.project_match_note && <p className="report-copy">{source.project_match_note}</p>}
        {sourceIndex === 0 && source.candidate_claim_excerpt && source.claim_scope !== "pdf_page" && <div className="claim-box"><b>Resume project summary</b><p>{source.candidate_claim_excerpt}</p></div>}
        {source.claim_comparison && source.project_identity_status === "confirmed" && source.claim_scope !== "pdf_page" && <div className="claim-check"><b>Details found in both the resume and project page</b><p>{source.claim_comparison.matched_terms.length} of {source.claim_comparison.claim_terms.length} descriptive terms also appeared on the public project page. This text comparison does not confirm who built the project or whether every feature works.</p>{source.claim_comparison.evidence?.length > 0 && <div className="match-terms">{source.claim_comparison.evidence.map((item:any)=><span key={item.term}>{item.term}</span>)}</div>}</div>}
        {source.claim_scope === "pdf_page" && <p className="project-meta">The resume link is embedded in a PDF. Its project description could not be tied to a specific text block on the page, so feature and technology claims from that page were not treated as verified.</p>}
        {source.manifest_files?.length > 0 && <p className="project-meta"><b>Project files reviewed:</b> {source.manifest_files.join(", ")}{source.source_files?.length ? `, plus ${source.source_files.length} code files sampled` : ""}</p>}
        {source.technologies?.length > 0 && <p className="project-meta"><b>Technologies found:</b> {source.technologies.join(", ")}</p>}
        {source.technology_checks?.length > 0 && <div className="technology-list"><b>Tools listed in the resume</b>{source.technology_checks.map((check:any) => <p className={check.status === "possible_mismatch" ? "review-flag" : ""} key={check.technology}><span>{check.technology}</span><span>{checkText(check.status)}</span></p>)}</div>}
        {source.checks && <details className="site-details"><summary>Website availability details</summary><p>HTTP {source.http_status || "—"} · page title {source.checks.html_title ? "found" : "missing"} · visible text {source.checks.visible_text ? "found" : "missing"} · This does not test buttons, forms, or logged-in features.</p></details>}
        {source.evidence?.length > 0 && <div className="public-evidence"><b>Relevant details found on the project page</b>{source.evidence.map((finding:any)=><p key={finding.criterion}>{finding.snippet}</p>)}</div>}
        </div>)}
      </article>)}</div> : candidate.project_urls?.length ? <div className="empty-projects"><b>{candidate.status === "not_shortlisted" ? "Project links found, checks not started" : ["deep_queued", "project_checking"].includes(candidate.status) ? "Project checks are in progress" : "No project check results saved"}</b><p>{candidate.status === "not_shortlisted" ? "Project checks run in stage two for candidates who advance from stage one. This resume did not advance, so its project links have not been checked." : "The resume contains these project URLs, but this batch has no completed check results for them yet."}</p><ul className="resume-link-list">{candidate.project_urls.map((url,index)=><li key={`${url}-${index}`}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul></div> : <div className="empty-projects"><b>No project links were found in the resume’s Projects section</b><p>Code-practice profiles and general contact links are excluded. Only project-linked GitHub repositories and hosted demos are checked.</p></div>}
      <div className="project-adjustment"><span>Score change from project checks</span><b>{candidate.project_score === null ? "Pending" : `${candidate.project_score > 0 ? "+" : ""}${candidate.project_score.toFixed(1)} points`}</b><small>Public information can support resume details. Missing or unclear information does not prove a claim is false.</small></div>
    </section>
    <div className="bottom-nav"><Link className="button button-small button-outline" href={`/batches/${batch.id}`}>Back to results</Link><span>{navigation.position ?? "—"} / {navigation.total}</span><Link className={`button button-small button-outline ${navigation.next ? "" : "is-disabled"}`} aria-disabled={!navigation.next} href={navigation.next ? `${base}${navigation.next}` : "#"}>Next candidate →</Link></div>
    <footer className="app-footer">Shortlist <span>·</span> Hiring team dashboard</footer>
    </div>
  </main>;
}
