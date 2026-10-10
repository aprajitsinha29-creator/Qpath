// One matched posting in the opportunities feed (plan 5.5). Needs an
// OpportunityItem plus the feed's first_visit and has_declared_skills flags;
// the match badge renders the score, "Not enough info" (no extracted skills),
// or an "Add your skills to see a match" link pointing at the on-page skills
// panel; NEW badge shows only when is_new && !first_visit.
import type { OpportunityItem } from '../../../types/api';

interface OpportunityCardProps {
  /** One item from GET /profiles/{id}/opportunities. */
  item: OpportunityItem;
  /** True when the whole feed is a first visit — NEW badges are suppressed. */
  firstVisit: boolean;
  /**
   * False when the profile declared no skills at all: a null match then means
   * "we can't compute one yet", so the card invites the user to the panel.
   */
  hasDeclaredSkills: boolean;
}

export function OpportunityCard({ item, firstVisit, hasDeclaredSkills }: OpportunityCardProps) {
  const showNewBadge = item.is_new && !firstVisit;
  // The skills panel is a sibling on OpportunitiesPage; scroll+focus it so a
  // keyboard user lands somewhere meaningful, not just at page top.
  const jumpToSkills = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const target = document.getElementById('skills-panel');
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const button = target?.querySelector<HTMLButtonElement>('button');
    button?.focus();
  };

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
          hasDeclaredSkills ? (
            // Profile declared skills but this posting has none extracted:
            // honest "we don't know" rather than a fabricated 0.
            <span
              data-testid="match-badge"
              className="rounded-full border border-amber-800/60 bg-amber-950/30 px-2.5 py-0.5 text-[10px] font-medium text-amber-200"
            >
              Not enough info
            </span>
          ) : (
            // No skills declared at all: match cannot exist — invite the user
            // to the skills panel instead of showing a percentage.
            <a
              href="#skills-panel"
              data-testid="match-badge"
              onClick={jumpToSkills}
              className="rounded-full border border-cyan-800/60 bg-cyan-950/30 px-2.5 py-0.5 text-[10px] font-medium text-cyan-200 hover:border-cyan-700 hover:bg-cyan-900/40"
            >
              Add your skills to see a match
            </a>
          )
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
