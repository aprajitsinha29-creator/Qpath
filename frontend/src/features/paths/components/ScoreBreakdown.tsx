// Renders three labeled bars (interest / demand / readiness) and the weights,
// so a reviewer can recompute the score by hand (plan 4.8 acceptance check).
// Needs a ScoreBreakdown payload from PathResult.
import type { ScoreBreakdown as ScoreBreakdownType } from '../../../types/api';

interface Props {
  breakdown: ScoreBreakdownType;
}

const BARS: { key: keyof Omit<ScoreBreakdownType, 'weights'>; label: string; color: string }[] = [
  { key: 'interest', label: 'Interest', color: 'bg-violet-500' },
  { key: 'demand', label: 'Demand', color: 'bg-cyan-500' },
  { key: 'readiness', label: 'Readiness', color: 'bg-emerald-500' },
];

/** Returns the weight percent for a dimension key (interest → W_INTEREST etc.). */
function weightFor(breakdown: ScoreBreakdownType, key: string): number {
  return breakdown.weights[key] ?? breakdown.weights[`W_${key.toUpperCase()}`] ?? 0;
}

export function ScoreBreakdown({ breakdown }: Props) {
  return (
    <div className="space-y-2" aria-label="Score breakdown">
      {BARS.map(({ key, label, color }) => {
        const value = breakdown[key] as number;
        const weight = weightFor(breakdown, key);
        return (
          <div key={key}>
            <div className="mb-0.5 flex justify-between text-[11px] text-slate-400">
              <span>
                {label} <span className="text-slate-500">({weight.toFixed(0)}%&nbsp;weight)</span>
              </span>
              <span className="tabular-nums text-slate-200">{value.toFixed(1)}</span>
            </div>
            <div
              className="h-2 w-full overflow-hidden rounded-full bg-slate-800"
              role="progressbar"
              aria-valuenow={value}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${label} score ${value.toFixed(1)} out of 100`}
            >
              <div
                className={`h-full rounded-full ${color}`}
                style={{ width: `${Math.min(value, 100)}%` }}
              />
            </div>
          </div>
        );
      })}
      <p className="pt-0.5 text-[10px] text-slate-500">
        Score&nbsp;=&nbsp;(Interest·{weightFor(breakdown, 'interest').toFixed(0)} + Demand·
        {weightFor(breakdown, 'demand').toFixed(0)} + Readiness·
        {weightFor(breakdown, 'readiness').toFixed(0)})&nbsp;/&nbsp;100
      </p>
    </div>
  );
}
