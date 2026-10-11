// Renders seniority and PhD/internship mix chips from a SubfieldDetail payload.
// Shows only the buckets that have non-zero counts.
// Needs seniority_mix record and phd_share number from the detail endpoint.
import type { SubfieldDetail } from '../../../types/api';

interface MixChipsProps {
  seniorityMix: SubfieldDetail['seniority_mix'];
  phdShare: SubfieldDetail['phd_share'];
  internshipPostings: number;
}

const SENIORITY_LABELS: Record<string, string> = {
  intern: 'Intern',
  entry: 'Entry',
  mid: 'Mid',
  senior: 'Senior',
  lead: 'Lead',
  postdoc: 'Post-doc',
  phd_student: 'PhD student',
  faculty: 'Faculty',
  unknown: 'Unspecified',
};

/** Renders seniority distribution chips and PhD/internship indicators. */
export function MixChips({ seniorityMix, phdShare, internshipPostings }: MixChipsProps) {
  const entries = Object.entries(seniorityMix).filter(([, count]) => count > 0);

  return (
    <section aria-label="Workforce mix">
      <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-400">
        Seniority mix
      </h4>

      {entries.length === 0 ? (
        <p className="text-xs italic text-slate-500">No seniority data extracted yet.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {entries.map(([key, count]) => (
            <span
              key={key}
              className="rounded-full border border-slate-700 bg-slate-800 px-2 py-0.5 text-[11px] text-slate-200"
            >
              {SENIORITY_LABELS[key] ?? key}&nbsp;
              <span className="font-semibold text-cyan-300">{count}</span>
            </span>
          ))}
        </div>
      )}

      {/* PhD and internship summary chips */}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {phdShare !== null && (
          <span
            title={`${Math.round(phdShare * 100)}% of postings that stated a requirement require a PhD`}
            className="rounded-full border border-indigo-800/60 bg-indigo-950/40 px-2 py-0.5 text-[11px] text-indigo-300"
          >
            PhD required: {Math.round(phdShare * 100)}%
          </span>
        )}
        {internshipPostings > 0 && (
          <span className="rounded-full border border-emerald-800/60 bg-emerald-950/40 px-2 py-0.5 text-[11px] text-emerald-300">
            {internshipPostings} internship{internshipPostings > 1 ? 's' : ''}
          </span>
        )}
      </div>
    </section>
  );
}
