// One matched posting in the opportunities feed (plan 5.5). Needs an
// OpportunityItem plus the response's first_visit flag; the match badge
// renders the score or "Not enough info" for null, and the NEW badge shows
// only when is_new && !first_visit (plan 5.5 — no badge shouting on first
// visit, an intro note covers that on the page instead).
import type { OpportunityItem } from '../../../types/api';

interface OpportunityCardProps {
  /** One item from GET /profiles/{id}/opportunities. */
  item: OpportunityItem;
  /** True when the whole feed is a first visit — NEW badges are suppressed. */
  firstVisit: boolean;
}

export function OpportunityCard({ item, firstVisit }: OpportunityCardProps) {
  const showNewBadge = item.is_new && !firstVisit;

  return (
    <article
      aria-label={`${item.title} at ${item.company}${item.is_internship ? ' (internship)' : ''}`}
      className="rounded-xl border border-slate-800 bg-slate-900/50 p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-white">{item.title}</h3>
          <p className="text-xs text-slate-400">{item.company}</p>
        </div>
        <span
          className={`flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            item.is_internship
              ? 'bg-indigo-950/50 text-indigo-200'
              : 'bg-slate-800/80 text-slate-400'
          }`}
        >
          {item.is_internship ? 'Internship' : 'Full-time'}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {item.match === null ? (
          <span
            data-testid="match-badge"
            className="rounded-full border border-amber-800/60 bg-amber-950/30 px-2.5 py-0.5 text-[10px] font-medium text-amber-200"
          >
            Not enough info
          </span>
        ) : (
          <span
            data-testid="match-badge"
            className="rounded-full bg-emerald-950/40 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-200"
          >
            {item.match}% match
          </span>
        )}
        {showNewBadge && (
          <span
            data-testid="new-badge"
            className="flex shrink-0 items-center rounded-full bg-cyan-950/40 px-2.5 py-0.5 text-[10px] font-semibold text-cyan-200"
          >
            NEW
          </span>
        )}
      </div>

      {item.matched_skills.length > 0 && (
        <p className="mt-2 text-[11px] text-slate-500">Skills: {item.matched_skills.join(', ')}</p>
      )}

      {item.apply_url ? (
        <a
          href={item.apply_url}
          rel="noopener noreferrer"
          target="_blank"
          className="mt-2 inline-block rounded-md bg-slate-800 px-3 py-1.5 text-[11px] font-medium text-slate-200 hover:bg-slate-700"
        >
          Apply
        </a>
      ) : (
        <span className="mt-2 text-[11px] text-slate-600">No apply link</span>
      )}
    </article>
  );
}
