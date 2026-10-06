// SubfieldDetailPage: full detail view for one quantum subfield at route
// /pulse/:subfieldId. Renders SkillBars, MixChips, ResearchFocus and a
// paginated posting list. Uses useSubfieldDetail hook for server state.
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { MixChips } from '../features/pulse/components/MixChips';
import { ResearchFocus } from '../features/pulse/components/ResearchFocus';
import { SkillBars } from '../features/pulse/components/SkillBars';
import { useSubfieldDetail } from '../features/pulse/hooks/usePulse';
import { formatNumber } from '../lib/format';
import type { PulseRegion } from '../types/api';

function isRegion(v: string | null): v is PulseRegion {
  return v === 'global' || v === 'india';
}

/** Full detail page for one subfield: skills, mix, research and postings. */
export function SubfieldDetailPage() {
  const { subfieldId } = useParams<{ subfieldId: string }>();
  const [searchParams] = useSearchParams();
  const regionParam = searchParams.get('region');
  const region: PulseRegion = isRegion(regionParam) ? regionParam : 'global';

  const { data, isLoading, isError, error } = useSubfieldDetail(subfieldId ?? '', region);

  if (!subfieldId) {
    return <p className="p-8 text-slate-400">Invalid subfield.</p>;
  }

  if (isLoading) {
    return (
      <div className="p-8" aria-busy="true" aria-label="Loading subfield detail">
        <div className="h-6 w-48 animate-pulse rounded bg-slate-700" />
        <div className="mt-4 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 w-full animate-pulse rounded-xl bg-slate-800" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !data) {
    const msg = error instanceof Error ? error.message : 'Unknown error';
    return (
      <div className="p-8" role="alert">
        <p className="font-semibold text-red-400">Failed to load subfield detail</p>
        <p className="mt-1 text-sm text-slate-400">{msg}</p>
        <Link
          to="/pulse"
          className="mt-4 inline-block rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
        >
          ← Back to Pulse
        </Link>
      </div>
    );
  }

  return (
    <article className="mx-auto max-w-3xl space-y-8 px-4 py-8">
      {/* Back link */}
      <Link
        to="/pulse"
        className="inline-block text-sm text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline focus:outline-none focus:ring-2 focus:ring-cyan-500"
      >
        ← Back to Market Pulse
      </Link>

      {/* Header */}
      <header>
        <div className="flex items-start gap-3">
          <h1 className="text-2xl font-bold text-white">{data.name}</h1>
          {data.low_data && (
            <span
              title="Fewer than 8 active postings — demand evidence is thin"
              className="mt-1 rounded border border-amber-800/60 bg-amber-950/40 px-1.5 py-0.5 text-[10px] font-medium text-amber-300"
            >
              low data
            </span>
          )}
        </div>
        <p className="mt-1 text-sm leading-relaxed text-slate-400">{data.description}</p>
      </header>

      {/* Counts row */}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="posting counts">
        {[
          { label: 'Active postings', value: data.active_postings, color: 'text-cyan-300' },
          { label: 'Internships', value: data.internship_postings, color: 'text-emerald-300' },
          {
            label: 'Extended-query',
            value: data.extra_postings,
            color: 'text-slate-300',
          },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className={`text-xl font-semibold ${color}`}>{formatNumber(value)}</dd>
          </div>
        ))}
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          <dt className="text-[11px] uppercase tracking-wide text-slate-500">Extraction</dt>
          <dd className="text-xl font-semibold text-slate-300">
            {Math.round(data.extraction_coverage * 100)}%
          </dd>
        </div>
      </dl>

      {/* Skills */}
      <SkillBars skills={data.top_skills} extractionCoverage={data.extraction_coverage} />

      {/* Seniority mix */}
      <MixChips
        seniorityMix={data.seniority_mix}
        phdShare={data.phd_share}
        internshipPostings={data.internship_postings}
      />

      {/* Research themes */}
      <ResearchFocus themes={data.themes} />

      {/* Postings */}
      <section aria-label="Job postings">
        <h4 className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-400">
          Job postings ({formatNumber(data.postings.length)})
        </h4>
        {data.postings.length === 0 ? (
          <p className="text-xs italic text-slate-500">No postings captured yet — run a refresh.</p>
        ) : (
          <ul className="space-y-3">
            {data.postings.map((p) => (
              <li
                key={p.id}
                className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold text-white">{p.title}</p>
                    <p className="text-slate-400">
                      {p.company}
                      {p.location ? ` · ${p.location}` : ''}
                      {p.via ? ` via ${p.via}` : ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    {p.is_internship && (
                      <span className="rounded border border-emerald-800/60 bg-emerald-950/40 px-1.5 py-0.5 text-[10px] text-emerald-300">
                        Internship
                      </span>
                    )}
                    {p.apply_url && (
                      <a
                        href={p.apply_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded border border-slate-700 px-2 py-0.5 text-[11px] text-cyan-400 hover:bg-slate-800"
                      >
                        Apply ↗
                      </a>
                    )}
                  </div>
                </div>
                {p.snippet && (
                  <p className="mt-2 text-xs leading-relaxed text-slate-500">{p.snippet}</p>
                )}
                <p className="mt-1 text-[11px] text-slate-600">
                  First seen {p.first_seen_at.slice(0, 10)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
