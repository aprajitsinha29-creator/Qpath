// Renders the "SerpApi activity" panel: mode, today's live-call budget and
// the most recent logged calls — making SerpApi's role in the data visible.
// Needs the SerpApiActivity payload from GET /meta/serpapi-activity.
import { formatNumber } from '../../../lib/format';
import { useSerpApiActivity } from '../hooks/usePulse';

export function SerpApiActivityPanel() {
  const { data, isLoading, isError } = useSerpApiActivity();

  if (isLoading) {
    return (
      <section
        aria-label="SerpApi activity"
        className="rounded-xl border border-slate-800 bg-slate-900/50 p-5"
      >
        <div
          role="status"
          aria-label="Loading SerpApi activity"
          className="h-24 animate-pulse rounded-lg bg-slate-800/70"
        />
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section
        aria-label="SerpApi activity"
        className="rounded-xl border border-slate-800 bg-slate-900/50 p-5"
      >
        <h2 className="text-sm font-semibold text-slate-200">SerpApi activity</h2>
        <p role="alert" className="mt-2 text-xs text-rose-300">
          Could not load SerpApi activity.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-label="SerpApi activity"
      className="rounded-xl border border-slate-800 bg-slate-900/50 p-5"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-200">SerpApi activity</h2>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${
            data.mode === 'fixtures'
              ? 'border-cyan-800/60 bg-cyan-950/40 text-cyan-300'
              : 'border-amber-800/60 bg-amber-950/40 text-amber-300'
          }`}
          title={
            data.mode === 'fixtures'
              ? 'Reading recorded responses; no credits spent'
              : 'Calling the live SerpApi API'
          }
        >
          {data.mode === 'fixtures' ? 'fixture mode' : 'live mode'}
        </span>
      </header>

      <p className="mt-2 text-xs text-slate-400">
        Live calls today:{' '}
        <span className="font-semibold text-slate-200">{formatNumber(data.live_calls_today)}</span>{' '}
        / {formatNumber(data.daily_cap)} cap
      </p>

      {data.recent_calls.length === 0 ? (
        <p className="mt-3 text-xs text-slate-500">No SerpApi calls logged yet.</p>
      ) : (
        <table className="mt-3 w-full text-left text-xs" aria-label="recent SerpApi calls">
          <caption className="sr-only">
            Most recent SerpApi calls with engine, query and status
          </caption>
          <thead className="text-slate-500">
            <tr>
              <th scope="col" className="py-1 pr-2 font-medium">
                Engine
              </th>
              <th scope="col" className="py-1 pr-2 font-medium">
                Query
              </th>
              <th scope="col" className="py-1 pr-2 font-medium">
                Source
              </th>
              <th scope="col" className="py-1 font-medium">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="text-slate-300">
            {data.recent_calls.slice(0, 10).map((call) => (
              <tr key={call.id} className="border-t border-slate-800/70">
                <td className="py-1 pr-2">{call.engine}</td>
                <td className="max-w-[12rem] truncate py-1 pr-2" title={call.query}>
                  {call.query}
                </td>
                <td className="py-1 pr-2">{call.source}</td>
                <td
                  className={`py-1 ${
                    call.status === 'ok' || call.status === 'empty'
                      ? 'text-emerald-400'
                      : 'text-amber-400'
                  }`}
                >
                  {call.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
