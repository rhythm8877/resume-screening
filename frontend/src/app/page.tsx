import Link from "next/link";
import { Brand, Icon, SectionHeading } from "@/components/ui";

const steps = [
  { number: "01", title: "Compare resumes", description: "Applications are compared with the job description and its requirements.", icon: "document" as const },
  { number: "02", title: "Review project links", description: "Check the specific repositories and demo websites listed on each resume.", icon: "link" as const },
  { number: "03", title: "Decide who advances", description: "Review each result and choose who should move forward in your process.", icon: "check" as const },
];

export default function Home() {
  return <main className="app-shell landing-shell">
    <header className="app-header landing-header"><Brand /><span className="landing-header-label">RESUME REVIEW</span><Link href="/dashboard" className="button button-primary landing-header-button">Open dashboard <Icon name="arrow-right" size={14} /></Link></header>

    <section className="landing-hero">
      <div className="landing-copy">
        <p className="eyebrow">CANDIDATE REVIEW FOR HIRING TEAMS</p>
        <h1>Review applications<br />with more context.</h1>
        <p>Compare resumes with the role, check candidates’ project links, and bring the results together in one review.</p>
        <div className="landing-actions"><Link href="/dashboard" className="button button-primary landing-primary">Create a screening batch <Icon name="arrow-right" size={15} /></Link><span>For one resume or a full batch</span></div>
      </div>
      <div className="landing-visual" aria-label="The three parts of a candidate review">
        <div className="landing-visual-top"><span>THE REVIEW</span><span>01 — 03</span></div>
        {steps.map((step, index) => <article className={`landing-visual-row ${index === 0 ? "is-current" : ""}`} key={step.number}><span className="landing-visual-number">{step.number}</span><span className="landing-visual-icon"><Icon name={step.icon} size={17} /></span><span className="landing-visual-text"><b>{step.title}</b><small>{step.description}</small></span><span className="landing-visual-arrow"><Icon name="arrow-right" size={14} /></span></article>)}
        <div className="landing-visual-footer"><span className="review-dot" />Hiring teams make the final decision</div>
      </div>
    </section>

    <section className="landing-section landing-how" id="how-it-works">
      <SectionHeading eyebrow="HOW IT WORKS" title="A straightforward review process" description="Move from the job description to a candidate shortlist in three clear steps." />
      <div className="landing-step-grid">{steps.map((step) => <article className="landing-step-card" key={step.number}><span className="landing-step-no">{step.number}</span><span className="landing-step-icon"><Icon name={step.icon} size={18} /></span><h3>{step.title}</h3><p>{step.description}</p></article>)}</div>
    </section>

    <section className="landing-section landing-review-details">
      <div className="landing-detail-copy"><p className="eyebrow">ONE REVIEW, ALL THE DETAILS</p><h2>See why a candidate moved forward.</h2><p>Each candidate page brings together the resume match, the selection status, and the public project links that were checked.</p><Link href="/dashboard" className="text-link">Start a review <Icon name="arrow-right" size={14} /></Link></div>
      <div className="landing-detail-list"><div><span className="detail-check"><Icon name="check" size={13} /></span><span><b>Resume match</b><small>Compare experience with the job requirements.</small></span></div><div><span className="detail-check"><Icon name="check" size={13} /></span><span><b>Project checks</b><small>See which linked repositories and demos were reached.</small></span></div><div><span className="detail-check"><Icon name="check" size={13} /></span><span><b>Clear outcome</b><small>Understand the candidate’s current status and next step.</small></span></div></div>
    </section>

    <section className="landing-cta"><div><p className="eyebrow">READY TO BEGIN</p><h2>Start with a role you’re hiring for.</h2><p>Add the job description, choose the shortlist sizes, and upload resumes.</p></div><Link href="/dashboard" className="button button-primary">Go to dashboard <Icon name="arrow-right" size={14} /></Link></section>
    <footer className="app-footer landing-footer"><Brand /><span>Candidate review for hiring teams</span></footer>
  </main>;
}
