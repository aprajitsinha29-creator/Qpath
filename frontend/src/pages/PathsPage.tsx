// Renders six ranked career paths with score breakdowns, evidence, and
// grounded AI explanations. Redirects to /diagnostic if no assessment exists.
// Needs GET /profiles/{id}/paths and POST /profiles/{id}/paths/explanations.
import { Link, Navigate } from 'react-router-dom';
import { useLatestAssessment } from '../features/diagnostic/hooks/useDiagnostic';
import { PathCard } from '../features/paths/components/PathCard';
import { usePaths, useRequestExplanations } from '../features/paths/hooks/usePaths';
import { DeclaredSkillsPanel } from '../features/skills/components/DeclaredSkillsPanel';
import { useProfile } from '../features/skills/hooks/useSkills';
import { useChosenPath } from '../features/tracker/hooks/useTracker';
import { getOrCreateProfileId } from '../lib/profileId';
import { formatDate } from '../lib/format';

export function PathsPage() {
  const profileId = getOrCreateProfileId();
  const { data, isLoading, isError, error } = usePaths(profileId);
  const explainMutation = useRequestExplanations(profileId);
  // Declared-skills panel (optional): its own query — a profile failure here
  // must not break the paths view; the picker is simply not rendered.
  const profileQuery = useProfile(profileId);
  // Tracked path id (Phase 5) feeds the TrackPathButton on each card; a
  // failed profile query only costs the button state, not the page.
  const chosenPathQuery = useChosenPath(profileId);
  // Taken-at date of the assessment the ranking is based on. The paths
  // payload itself does not carry the date, so it comes from the latest
  // assessment query; rendering it is best-effort (hidden while loading/failing).
  const latestAssessmentQuery = useLatestAssessment(profileId);

  // 409 assessment_required → redirect to diagnostic with a message (plan 4.6)
  const status = (error as { status?: number } | null)?.status;
  if (isError && status === 409) {
    return (
      <Navigate
        to="/diagnostic"
        state={{
          message:
            'You need to take the orientation diagnostic first so we can rank career paths based on your readiness and interest.',
        }}
        replace
      />
    );
  }

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading career paths" className="space-y-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-48 animate-pulse rounded-xl bg-slate-800/60" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400"
      >
        <p>Could not load career paths.</p>
        <p className="mt-1 text-xs text-slate-500">
          {error instanceof Error ? error.message : 'The API request failed.'}
        </p>
        <Link
          to="/diagnostic"
          className="mt-4 inline-block rounded-md bg-cyan-600 px-4 py-2 font-semibold text-white hover:bg-cyan-500"
        >
          Take the diagnostic
        </Link>
      </div>
    );
  }

  if (!data || data.paths.length === 0) {
    return (
      <div
        role="status"
        className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400"
      >
        <p>No paths found. Take the diagnostic first.</p>
        <Link
          to="/diagnostic"
          className="mt-4 inline-block rounded-md bg-cyan-600 px-4 py-2 font-semibold text-white hover:bg-cyan-500"
        >
          Take the diagnostic
        </Link>
      </div>
    );
  }

  const allHaveExplanations = data.paths.every((p) => p.explanation !== null);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Career Paths</h1>
          <p className="mt-1 text-sm text-slate-400">
            Ranked by a blend of your interest, field demand, and readiness score.
          </p>
          {latestAssessmentQuery.data?.taken_at && (
            <p className="mt-1 text-xs text-slate-500">
              {`Based on your assessment from ${formatDate(latestAssessmentQuery.data.taken_at)}`}
            </p>
          )}
          {data.saturation_note && (
            <p className="mt-1 text-xs text-amber-400">{data.saturation_note}</p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => explainMutation.mutate()}
            disabled={explainMutation.isPending || allHaveExplanations}
            className="rounded-md bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-600 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {explainMutation.isPending ? 'Generating…' : 'Generate Explanations'}
          </button>

          <Link
            to="/diagnostic/results"
            className="text-sm text-slate-400 underline hover:text-slate-300"
          >
            ← Results
          </Link>
        </div>
      </div>

      {/* Error from explanation mutation (non-fatal — templates are used server-side) */}
      {explainMutation.isError && (
        <div
          role="alert"
          className="rounded border border-red-800/60 bg-red-950/30 p-3 text-xs text-red-300"
        >
          Explanation generation failed. Try again or see the template summaries below.
        </div>
      )}

      {/* Declared skills (carry-over): pre-filled from the profile; only rendered
          when the profile loads — the panel hides quietly otherwise */}
      {profileQuery.data && (
        <DeclaredSkillsPanel
          profileId={profileId}
          profileSkills={profileQuery.data.declared_skills}
        />
      )}

      {/* Path cards */}
      <div className="space-y-4" aria-label="Ranked career paths">
        {data.paths.map((path) => (
          <PathCard
            key={path.path_id}
            path={path}
            explanationLoading={explainMutation.isPending}
            trackedPathId={chosenPathQuery.data?.chosen_path_id ?? null}
            profileId={profileId}
          />
        ))}
      </div>

      {/* Table alternative for accessibility (charts rule AGENTS 3.6.6 applied to the breakdown bars) */}
      <details className="text-xs text-slate-500">
        <summary className="cursor-pointer hover:text-slate-400">
          Score table (text alternative)
        </summary>
        <table className="mt-2 w-full border-collapse text-left" aria-label="Score breakdown table">
          <thead>
            <tr className="border-b border-slate-800">
              <th className="py-1 pr-3 font-medium">Rank</th>
              <th className="py-1 pr-3 font-medium">Path</th>
              <th className="py-1 pr-3 font-medium tabular-nums">Score</th>
              <th className="py-1 pr-3 font-medium tabular-nums">Interest</th>
              <th className="py-1 pr-3 font-medium tabular-nums">Demand</th>
              <th className="py-1 pr-3 font-medium tabular-nums">Readiness</th>
            </tr>
          </thead>
          <tbody>
            {data.paths.map((p) => (
              <tr key={p.path_id} className="border-b border-slate-900">
                <td className="py-1 pr-3">{p.rank}</td>
                <td className="py-1 pr-3">{p.title}</td>
                <td className="py-1 pr-3 tabular-nums">{p.score.toFixed(1)}</td>
                <td className="py-1 pr-3 tabular-nums">{p.breakdown.interest.toFixed(1)}</td>
                <td className="py-1 pr-3 tabular-nums">{p.breakdown.demand.toFixed(1)}</td>
                <td className="py-1 pr-3 tabular-nums">{p.breakdown.readiness.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
