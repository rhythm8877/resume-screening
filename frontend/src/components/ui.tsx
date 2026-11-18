import Link from "next/link";
import type { ReactNode } from "react";

export type IconName = "arrow-right" | "briefcase" | "check" | "document" | "external" | "link" | "search" | "upload";

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true as const };
  const drawings: Record<IconName, ReactNode> = {
    "arrow-right": <><path d="M4 12h15" /><path d="m13 5 7 7-7 7" /></>,
    briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    document: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h8" /></>,
    external: <><path d="M14 3h7v7M10 14 21 3" /><path d="M19 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6" /></>,
    link: <><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7.1-7.1l-1.7 1.7" /><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7.1 7.1l1.7-1.7" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    upload: <><path d="M12 16V4m0 0L7 9m5-5 5 5" /><path d="M4 16v4h16v-4" /></>,
  };
  return <svg {...common}>{drawings[name]}</svg>;
}

export function Brand({ href = "/" }: { href?: string }) {
  return <Link className="brand" href={href}><img className="brand-mark" src="/shortlist-mark.svg" alt="" /><span>Shortlist</span></Link>;
}

export function SectionHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="ui-section-heading"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2>{description && <p className="section-description">{description}</p>}</div>{action}</div>;
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  const safeValue = Math.max(0, Math.min(100, value));
  return <div className="ui-progress" role="progressbar" aria-label={label} aria-valuenow={safeValue} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${safeValue}%` }} /></div>;
}

export function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "active" | "success" | "warning" | "danger" }) {
  return <span className={`ui-status ui-status-${tone}`}><i aria-hidden="true" />{children}</span>;
}
