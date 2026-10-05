// Renders the Market Pulse page: header controls (region toggle, internship
// filter, dev-only refresh), the six subfield cards and the SerpApi activity
// panel. Needs GET /pulse for the active region; each region fetch has its
// own loading, empty and error state (AGENTS.md 3.6.4).
import { useState } from 'react';
import { InternshipFilter } from '../features/pulse/components/InternshipFilter';
import { RefreshButton } from '../features/pulse/components/RefreshButton';
import { RegionToggle } from '../features/pulse/components/RegionToggle';
import { SerpApiActivityPanel } from '../features/pulse/components/SerpApiActivityPanel';
import { SubfieldCard } from '../features/pulse/components/SubfieldCard';
import { usePulseCards } from '../features/pulse/hooks/usePulse';
import type { PulseRegion } from '../types/api';

export function PulsePage() {
  const [region, setRegion] = useState<PulseRegion>('global');
  const [internshipOnly, setInternshipOnly] = useState(false);

  const { data: cards, isLoading, isError, error } = usePulseCards(region);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4">
        <div className="max-w-3xl space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Quantum Market Pulse
          </h1>
          <p className="text-sm leading-relaxed text-slate-400">
            Live posting volume per quantum subfield, captured from Google Jobs via SerpApi. Counts
            are sampled (page-capped), not exhaustive — cards flagged "low data" have thin demand
            evidence.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4">
            <RegionToggle value={region} onChange={setRegion} disabled={isLoading} />
            <InternshipFilter value={internshipOnly} onChange={setInternshipOnly} />
          </div>
          {/* Dev-only affordance: asks for the admin token on first use. */}
          <RefreshButton region={region} />
        </div>
      </div>

      {isLoading ? (
        <div
          role="status"
          aria-label="Loading pulse cards"
          className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
        >
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-56 animate-pulse rounded-xl bg-slate-800/60" />
          ))}
        </div>
      ) : isError ? (
        <div
          role="alert"
          className="rounded-xl border border-rose-900/60 bg-rose-950/40 p-6 text-sm text-rose-200"
        >
          <h2 className="font-semibold">Could not load Market Pulse</h2>
          <p className="mt-1 text-xs">
            {error instanceof Error ? error.message : 'The API request failed.'} Is the backend
            running?
          </p>
        </div>
      ) : !cards || cards.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400">
          No pulse data captured yet — run a refresh (dev-only button above).
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => (
            <SubfieldCard
              key={card.subfield_id}
              card={card}
              region={region}
              internshipOnly={internshipOnly}
            />
          ))}
        </div>
      )}

      <SerpApiActivityPanel />
    </div>
  );
}
