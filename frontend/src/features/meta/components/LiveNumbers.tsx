// Renders the "Live numbers" block for the Method page: SerpApi calls by
// engine (live vs offline recorded fixtures), posting totals, extraction
// coverage, research
// themes, and last refresh times. Needs the MethodStatsResponse query result
// (data/loading/error); every number is displayed exactly as returned.
import { formatDate, formatNumber, formatPercent } from '../../../lib/format';
import type { MethodStatsResponse } from '../../../types/api';

interface LiveNumbersProps {
  data: MethodStatsResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-cyan-300">{value}</dd>
    </div>
  );
}

export function LiveNumbers({ data, isLoading, isError, onRetry }: LiveNumbersProps) {
  if (isLoading) {
    return (
      <div role="status" aria-label="Loading live numbers" className="space-y-3">
        <div className="h-24 animate-pulse rounded-xl bg-slate-800/60" />
        <div className="h-16 animate-pulse rounded-xl bg-slate-800/60" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div
        role="alert"
        className="space-y-2 rounded-xl border border-red-800/60 bg-red-950/30 p-4 text-sm text-red-200"
      >
        <p>Could not load the live numbers.</p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md bg-red-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const engines = Object.entries(data.serpapi_calls);
  const extractionCoverage =
    data.postings_total > 0 ? data.extraction_done / data.postings_total : null;

  return (
    <section aria-label="Live numbers" data-testid="live-numbers" className="space-y-4">
      <h2 className="text-lg font-semibold text-white">Live numbers</h2>

      {/* SerpApi usage honesty block: per engine, live vs offline (recorded fixtures). */}
      {engines.length === 0 ? (
        <p role="status" className="text-sm text-slate-400">
          No SerpApi calls logged yet — nothing has been ingested on this instance.
        </p>
      ) : (
        <ul className="space-y-2" aria-label="SerpApi calls by engine">
          {engines.map(([engine, counts]) => (
            <li
              key={engine}
              className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-300"
            >
              <span className="font-medium text-white">{engine}</span> — {formatNumber(counts.live)}{' '}
              live call{counts.live === 1 ? '' : 's'}, {formatNumber(counts.fixture)} offline
              (recorded fixtures)
            </li>
          ))}
        </ul>
      )}

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat label="Postings captured" value={formatNumber(data.postings_total)} />
        <Stat label="Postings active" value={formatNumber(data.postings_active)} />
        <Stat
          label="Extraction coverage"
          value={extractionCoverage === null ? 'n/a' : formatPercent(extractionCoverage)}
        />
        <Stat label="Research themes" value={formatNumber(data.themes_count)} />
        <Stat
          label="Last jobs refresh"
          value={data.last_jobs_refresh ? formatDate(data.last_jobs_refresh) : 'never'}
        />
        <Stat
          label="Last Scholar refresh"
          value={data.last_scholar_refresh ? formatDate(data.last_scholar_refresh) : 'never'}
        />
      </dl>
    </section>
  );
}
