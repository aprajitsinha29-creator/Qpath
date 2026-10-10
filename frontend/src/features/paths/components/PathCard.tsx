// Renders one ranked career path card: rank badge (top-3 highlighted),
// total score, ScoreBreakdown bars, EvidencePanel, ExplanationBlock,
// LowDataNotice, and the Phase 5 TrackPathButton. Needs a PathResult, an
// explanationLoading flag, and the profile's currently tracked path id
// (null until one is tracked) to label the button.
import { useState } from 'react';
import type { PathResult } from '../../../types/api';
import { TrackPathButton } from '../../tracker/components/TrackPathButton';
import { EvidencePanel } from './EvidencePanel';
import { ExplanationBlock } from './ExplanationBlock';
import { LowDataNotice } from './LowDataNotice';
import { ScoreBreakdown } from './ScoreBreakdown';

interface Props {
  path: PathResult;
  /** True while the batched explanation mutation is in-flight. */
  explanationLoading: boolean;
  /** Profile's tracked path id (Phase 5); null unless one is tracked. */
  trackedPathId?: string | null;
  /** Anonymous profile id the tracking mutation is keyed on. */
  profileId?: string;
}

export function PathCard({ path, explanationLoading, trackedPathId = null, profileId }: Props) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [explanationOpen, setExplanationOpen] = useState(false);

  const isTop = path.is_top3;

  return (
    <article
      aria-label={`${path.title} — rank ${path.rank}`}
      className={`flex flex-col gap-3 rounded-xl border p-5 shadow-lg ${
        isTop ? 'border-cyan-700/60 bg-cyan-950/20' : 'border-slate-800 bg-slate-900/50'
      }`}
    >
      {/* Header: rank badge + title + score */}
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            aria-label={`Rank ${path.rank}`}
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
              isTop ? 'bg-cyan-600 text-white' : 'bg-slate-800 text-slate-400'
            }`}
          >
            {path.rank}
          </span>
          <div>
            <h2 className="text-base font-semibold text-white">{path.title}</h2>
            {isTop && (
              <span className="text-[10px] font-medium uppercase tracking-wide text-cyan-400">
                Top match
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1 text-right">
          <span
            className="text-2xl font-bold tabular-nums text-white"
            aria-label={`Score ${path.score.toFixed(1)}`}
          >
            {path.score.toFixed(1)}
          </span>
          <span className="text-[11px] text-slate-500">/ 100</span>
        </div>
      </header>

      {/* Track-this-path / Tracking button (plan 5.5); switching is allowed. */}
      {profileId && (
        <div>
          <TrackPathButton
            profileId={profileId}
            pathId={path.path_id}
            trackedPathId={trackedPathId}
          />
        </div>
      )}

      {/* Low-data notice */}
      {path.low_data && <LowDataNotice />}

      {/* Score breakdown bars */}
      <ScoreBreakdown breakdown={path.breakdown} />

      {/* Evidence panel (collapsible) */}
      <div>
        <button
          type="button"
          onClick={() => setEvidenceOpen((o) => !o)}
          aria-expanded={evidenceOpen}
          className="text-xs font-medium text-cyan-400 underline underline-offset-2 hover:text-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-500 rounded"
        >
          {evidenceOpen ? 'Hide evidence' : 'Show evidence'}
        </button>
        {evidenceOpen && (
          <div className="mt-2">
            <EvidencePanel evidence={path.evidence} />
          </div>
        )}
      </div>

      {/* Explanation (collapsible) */}
      <div>
        <button
          type="button"
          onClick={() => setExplanationOpen((o) => !o)}
          aria-expanded={explanationOpen}
          className="text-xs font-medium text-violet-400 underline underline-offset-2 hover:text-violet-300 focus:outline-none focus:ring-2 focus:ring-violet-500 rounded"
        >
          {explanationOpen ? 'Hide explanation' : 'Show explanation'}
        </button>
        {explanationOpen && (
          <div className="mt-2">
            <ExplanationBlock
              explanation={path.explanation}
              isLoading={explanationLoading && !path.explanation}
            />
          </div>
        )}
      </div>
    </article>
  );
}
