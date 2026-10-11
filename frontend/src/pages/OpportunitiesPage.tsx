// OpportunitiesPage: the Phase 5 opportunity feed (plan 5.5). Self-contained:
// reads the anonymous profile id from storage, gates on the tracked path
// (redirects to /paths when none), owns the region/internship filters, the
// "Mark all as seen" action, the SkillPicker panel, and loading/empty/error
// states per frontend rules 3.6.4.
import { useMemo, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { formatRelativeTime } from '../lib/format';
import { LastRefreshedPill } from '../features/tracker/components/LastRefreshedPill';
import { OpportunityCard } from '../features/tracker/components/OpportunityCard';
import { useMarkSeen, useOpportunities } from '../features/tracker/hooks/useTracker';
import { SkillPicker } from '../features/skills/components/SkillPicker';
import { useProfile } from '../features/skills/hooks/useSkills';
import { useTaxonomy } from '../features/pulse/hooks/usePulse';
import type { OpportunityItem } from '../types/api';
import { getOrCreateProfileId } from '../lib/profileId';

/**
 * Feed display order (plan 5.5 + user spec): match desc when skill data
 * exists, otherwise (no declared skills → match is null for everything)
 * fall back to first_seen desc so the feed still means "newest first".
 * Posting id breaks exact-timestamp ties for determinism.
 */
function sortForDisplay(items: OpportunityItem[], hasDeclaredSkills: boolean): OpportunityItem[] {
  const sorted = [...items];
  if (!hasDeclaredSkills) {
    return sorted.sort(
      (a, b) =>
        Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at) || a.posting_id - b.posting_id,
    );
  }
  return sorted; // backend already sorted: match desc, nulls last, first_seen desc
}

export function OpportunitiesPage() {
  const profileId = getOrCreateProfileId();
  const [region, setRegion] = useState<'global' | 'india'>('global');
  const [internshipFilter, setInternshipFilter] = useState<'all' | 'only' | 'exclude'>('all');
  const [skillsOpen, setSkillsOpen] = useState(false);

  const internshipParam =
    internshipFilter === 'all' ? null : internshipFilter === 'only' ? true : false;

  const { data, isLoading, isError, error, refetch } = useOpportunities(
    profileId,
    region,
    internshipParam,
  );
  const markSeenMutation = useMarkSeen(profileId);
  // Declared skills for the SkillPicker pre-fill; a profile failure here must
  // not break the feed — the panel simply hides.
  const profileQuery = useProfile(profileId);
  // Path title for the subtitle (id alone reads like jargon); taxonomy cache
  // is shared with the pulse feature.
  const taxonomyQuery = useTaxonomy();

  const hasDeclaredSkills = (profileQuery.data?.declared_skills.length ?? 0) > 0;
  const displayItems = useMemo(
    () => (data ? sortForDisplay(data.items, hasDeclaredSkills) : []),
    [data, hasDeclaredSkills],
  );
  const pathTitle = taxonomyQuery.data?.career_paths.find((p) => p.id === data?.path_id)?.title;

  // 409 path_required → walk the user back to the path matcher (plan 5.5).
  const status = (error as { status?: number } | null)?.status;
  if (isError && status === 409) {
    return (
      <Navigate
        to="/paths"
        state={{
          message: 'Track a career path first so we can match its postings against your profile.',
        }}
        replace
      />
    );
  }

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading opportunities" className="mx-auto max-w-4xl space-y-4">
        <div className="h-16 animate-pulse rounded-xl bg-slate-800/60" />
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-800/60" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="mx-auto max-w-4xl space-y-3 rounded-xl border border-red-800/60 bg-red-950/30 p-4 text-sm text-red-200"
      >
        <p>Could not load opportunities.</p>
        <p className="text-xs text-red-300">
          {error instanceof Error ? error.message : 'Request failed.'}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-md bg-red-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return null; // Unreachable: TanStack Query keeps data from the last run.
  }

  const internshipLabel =
    internshipFilter === 'only'
      ? 'Internships only'
      : internshipFilter === 'exclude'
        ? 'No internships'
        : 'All postings';

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Opportunities</h1>
          {/* Human-readable path title; the raw id never shows in the UI. */}
          <p className="text-sm text-slate-400">
            {pathTitle ? `Matched to your tracked path: ${pathTitle}` : null} ·{' '}
            {region === 'global' ? 'Global' : 'India'}
          </p>
        </div>

        <button
          type="button"
          onClick={() => markSeenMutation.mutate()}
          disabled={markSeenMutation.isPending}
          data-testid="mark-seen-button"
          className="rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {markSeenMutation.isPending ? 'Saving…' : 'Mark all as seen'}
        </button>
      </div>

      {/* Filters: region + internship (plan 5.5). Labels on every control. */}
      <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-3">
        <div>
          <label htmlFor="region-filter" className="block text-xs font-medium text-slate-400">
            Region
          </label>
          <select
            id="region-filter"
            value={region}
            onChange={(e) => setRegion(e.target.value as 'global' | 'india')}
            className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
          >
            <option value="global">Global</option>
            <option value="india">India</option>
          </select>
        </div>
        <div>
          <label htmlFor="internship-filter" className="block text-xs font-medium text-slate-400">
            Internships
          </label>
          <select
            id="internship-filter"
            value={internshipFilter}
            onChange={(e) => setInternshipFilter(e.target.value as 'all' | 'only' | 'exclude')}
            className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
          >
            <option value="all">Include everything</option>
            <option value="only">Internships only</option>
            <option value="exclude">Exclude internships</option>
          </select>
        </div>
        <span className="ml-auto text-[11px] text-slate-500">{internshipLabel}</span>
      </div>

      {/* First visit: an intro note instead of NEW badges (plan 5.5). On a
          first visit last_seen_at is null and the badges would shout on every
          row — the note explains they will light up after "Mark all as seen". */}
      {data.first_visit ? (
        <div
          role="status"
          className="rounded-xl border border-emerald-800/40 bg-emerald-950/20 p-3 text-xs text-emerald-200"
        >
          <p className="font-semibold">First visit</p>
          <p className="mt-0.5">
            This is everything matching your tracked path so far. After you click &quot;Mark all as
            seen&quot;, postings that arrive afterwards will be highlighted as NEW.
          </p>
        </div>
      ) : null}

      {/* Declared skills (carry-over): collapsible; after saving, refetch the
          feed so match scores update with the freshly declared set. The id is
          the anchor OpportunityCard's "add your skills" link scrolls to. */}
      <div id="skills-panel" className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
        <button
          type="button"
          onClick={() => setSkillsOpen((open) => !open)}
          aria-expanded={skillsOpen}
          className="text-xs font-medium text-cyan-400 underline underline-offset-2 hover:text-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-500 rounded"
        >
          {skillsOpen ? 'Hide declared skills' : 'Update declared skills'}
        </button>
        {skillsOpen && profileQuery.data && (
          <div className="mt-2">
            <SkillPicker profileId={profileId} profileSkills={profileQuery.data.declared_skills} />
          </div>
        )}
      </div>

      {/* Feed listing (empty state included) */}
      {data.items.length === 0 ? (
        <div
          role="status"
          className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400"
        >
          <p>No matched postings yet.</p>
          <p className="mt-1 text-xs text-slate-500">
            Data refreshes automatically once tracked — check back after the next refresh.
          </p>
          <Link
            to="/"
            className="mt-4 inline-block rounded-md bg-cyan-600 px-4 py-2 font-semibold text-white hover:bg-cyan-500"
          >
            ← Back to Pulse
          </Link>
        </div>
      ) : (
        <div className="space-y-2" aria-label="Opportunities list">
          {displayItems.map((item) => (
            <OpportunityCard
              key={item.posting_id}
              item={item}
              firstVisit={data.first_visit}
              hasDeclaredSkills={hasDeclaredSkills}
            />
          ))}
        </div>
      )}

      {/* Footer meta: refresh status + totals. last_seen_at shows when the
          seen marker was last set (never by a GET, only by POST /seen). */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <div className="flex flex-wrap items-center gap-3">
          <LastRefreshedPill iso={data.last_refreshed_at} />
          {data.last_seen_at ? (
            <span>last seen {formatRelativeTime(data.last_seen_at)}</span>
          ) : null}
        </div>
        <div>
          {data.total} posting{data.total === 1 ? '' : 's'} in total
        </div>
      </div>
    </div>
  );
}
