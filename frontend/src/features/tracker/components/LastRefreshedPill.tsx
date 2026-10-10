// "Last refreshed" status pill for the opportunities feed (plan 5.5). Needs
// the latest successful jobs-refresh ISO timestamp; shows a relative time, or
// an explicit "never refreshed" state when the value is null.
import { formatRelativeTime } from '../../../lib/format';

interface LastRefreshedPillProps {
  /** Latest successful jobs refresh_runs.finished_at (ISO), or null. */
  iso: string | null;
}

export function LastRefreshedPill({ iso }: LastRefreshedPillProps) {
  if (!iso) {
    return (
      <span
        data-testid="last-refreshed-pill"
        className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 text-[10px] font-medium text-slate-500"
      >
        <span aria-hidden="true">⟳</span> never refreshed
      </span>
    );
  }

  return (
    <span
      data-testid="last-refreshed-pill"
      title={iso}
      className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 text-[10px] font-medium text-slate-300"
    >
      <span aria-hidden="true">⟳</span> refreshed {formatRelativeTime(iso)}
    </span>
  );
}
