// Renders posting counts, top-skills list, PhD share, and up to 3 sample
// postings with apply links for a single path (plan 4.6 EvidencePanel).
// Needs a PathEvidence payload.
import type { PathEvidence as PathEvidenceType } from '../../../types/api';
import { formatNumber } from '../../../lib/format';

interface Props {
  evidence: PathEvidenceType;
}

export function EvidencePanel({ evidence }: Props) {
  return (
    <div className="space-y-3">
      {/* Posting counts */}
      <dl className="grid grid-cols-2 gap-2 text-sm" aria-label="Posting counts">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
          <dt className="text-[11px] uppercase tracking-wide text-slate-500">Active postings</dt>
          <dd className="text-lg font-semibold text-cyan-300" data-testid="evidence-active">
            {formatNumber(evidence.active_postings)}
          </dd>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
          <dt className="text-[11px] uppercase tracking-wide text-slate-500">Internships</dt>
          <dd className="text-lg font-semibold text-emerald-300" data-testid="evidence-internship">
            {formatNumber(evidence.internship_postings)}
          </dd>
        </div>
      </dl>

      {/* PhD share */}
      {evidence.phd_share_pct !== null && (
        <p className="text-xs text-slate-400">
          <span className="text-slate-500">PhD required: </span>
          <span className="tabular-nums text-slate-200">{evidence.phd_share_pct.toFixed(1)}%</span>
          <span className="text-slate-500"> of postings</span>
        </p>
      )}

      {/* Top skills */}
      {evidence.top_skills.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Top skills</p>
          <ul className="space-y-1" aria-label="Top skills">
            {evidence.top_skills.map((s) => (
              <li key={s.skill_id} className="flex items-center gap-2 text-xs">
                <div
                  className="h-1.5 rounded-full bg-cyan-600"
                  style={{
                    width: `${Math.min(s.share_pct, 100)}%`,
                    minWidth: '4px',
                    maxWidth: '80px',
                  }}
                  aria-hidden="true"
                />
                <span className="text-slate-200">{s.name}</span>
                <span className="tabular-nums text-slate-500">{s.share_pct.toFixed(1)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sample postings */}
      {evidence.sample_postings.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Sample postings</p>
          <ul className="space-y-1" aria-label="Sample postings">
            {evidence.sample_postings.map((p) => (
              <li key={p.id} className="text-xs">
                {p.apply_url ? (
                  <a
                    href={p.apply_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-cyan-400 underline hover:text-cyan-300"
                  >
                    {p.title}
                  </a>
                ) : (
                  <span className="text-slate-300">{p.title}</span>
                )}
                <span className="ml-1 text-slate-500">— {p.company}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
