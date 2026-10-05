// Renders an expandable list of postings for one subfield: title, company,
// apply link (new tab, rel=noopener) and snippet. Needs the subfield id,
// active region and internship filter; fetches its own page of data.
import { formatNumber } from '../../../lib/format';
import { usePostings } from '../hooks/usePulse';
import type { PulseRegion } from '../../../types/api';

interface PostingListProps {
  subfieldId: string;
  region: PulseRegion;
  internshipOnly: boolean;
}

const PAGE_SIZE = 10;

export function PostingList({ subfieldId, region, internshipOnly }: PostingListProps) {
  // undefined internship = no filter; the backend treats absent as "everything".
  const internship = internshipOnly ? true : undefined;
  const { data, isLoading, isError, error } = usePostings(subfieldId, {
    region,
    internship,
    limit: PAGE_SIZE,
  });

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading postings" className="space-y-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-14 animate-pulse rounded-lg bg-slate-800/70" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-rose-900/60 bg-rose-950/40 p-3 text-xs text-rose-300"
      >
        Could not load postings: {error instanceof Error ? error.message : 'unknown error'}
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <p className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400">
        {internshipOnly
          ? 'No internship postings captured yet.'
          : 'No postings captured yet — run a refresh.'}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-slate-500" aria-live="polite">
        Showing {data.items.length} of {formatNumber(data.total)} postings
      </p>
      <ul className="space-y-2" aria-label="posting list">
        {data.items.map((posting) => (
          <li
            key={posting.id}
            className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium text-slate-100">{posting.title}</span>
              {posting.apply_url ? (
                <a
                  href={posting.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded border border-cyan-800/60 px-2 py-0.5 text-xs text-cyan-300 hover:bg-cyan-950/40 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                >
                  Apply ↗
                </a>
              ) : (
                <span className="text-xs text-slate-600">no link</span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-slate-400">
              {posting.company}
              {posting.location ? ` · ${posting.location}` : ''}
              {posting.via ? ` · via ${posting.via}` : ''}
              {posting.is_internship ? (
                <span className="ml-2 rounded bg-emerald-950/60 px-1 text-[10px] text-emerald-300">
                  internship
                </span>
              ) : null}
            </p>
            {posting.snippet ? (
              <p className="mt-1 line-clamp-2 text-xs text-slate-500">{posting.snippet}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
