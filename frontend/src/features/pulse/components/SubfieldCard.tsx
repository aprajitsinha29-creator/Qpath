// Renders one Market Pulse card: demand counts, tracking info, top companies
// and an expandable posting list. Needs a PulseCard payload plus the active
// region and an internship filter to pass through to the posting list.
import { useState } from 'react';
import { formatNumber } from '../../../lib/format';
import type { PulseCard as PulseCardType, PulseRegion } from '../../../types/api';
import { PostingList } from './PostingList';

interface SubfieldCardProps {
  card: PulseCardType;
  region: PulseRegion;
  internshipOnly: boolean;
}

export function SubfieldCard({ card, region, internshipOnly }: SubfieldCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article
      aria-label={`${card.name} market pulse`}
      className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-900/50 p-5 shadow-lg"
    >
      <header className="flex items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-white">{card.name}</h3>
        {card.low_data ? (
          <span
            title="Fewer than 8 active postings captured — demand evidence is thin"
            className="rounded border border-amber-800/60 bg-amber-950/40 px-1.5 py-0.5 text-[10px] font-medium text-amber-300"
          >
            low data
          </span>
        ) : null}
      </header>

      <p className="text-xs leading-relaxed text-slate-400">{card.description}</p>

      <dl className="grid grid-cols-2 gap-2 text-sm" aria-label="posting counts">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
          <dt className="text-[11px] uppercase tracking-wide text-slate-500">Active postings</dt>
          <dd className="text-lg font-semibold text-cyan-300" data-testid="active-postings">
            {formatNumber(card.active_postings)}
          </dd>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
          <dt className="text-[11px] uppercase tracking-wide text-slate-500">Internships</dt>
          <dd className="text-lg font-semibold text-emerald-300" data-testid="internship-postings">
            {formatNumber(card.internship_postings)}
          </dd>
        </div>
      </dl>

      {/* new_this_week is null until 2+ ingestion days exist; then we show
          "tracking since <date>" instead of a misleading number (plan 1.4). */}
      <p className="text-xs text-slate-400" data-testid="new-this-week">
        {card.new_this_week === null ? (
          card.tracking_since ? (
            <span>
              Tracking since <span className="text-slate-200">{card.tracking_since}</span>
            </span>
          ) : (
            <span>No postings captured yet</span>
          )
        ) : (
          <span>
            <span className="font-semibold text-cyan-300">+{card.new_this_week}</span> new this week
          </span>
        )}
      </p>

      {card.top_companies.length > 0 ? (
        <div className="text-xs text-slate-400">
          <span className="text-slate-500">Top companies: </span>
          <span className="text-slate-200">{card.top_companies.join(', ')}</span>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setExpanded((open) => !open)}
        aria-expanded={expanded}
        className="self-start rounded-md border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500"
      >
        {expanded ? 'Hide postings' : 'View postings'}
      </button>

      {expanded ? (
        <PostingList
          subfieldId={card.subfield_id}
          region={region}
          internshipOnly={internshipOnly}
        />
      ) : null}
    </article>
  );
}
