// Inline SVG sparkline of a subfield's daily active-posting trend (plan 5.5).
// Renders only with >= 2 snapshots; with 1 shows "tracking started <date>";
// with 0 shows "no history yet". Exposes a text alternative via role="img"
// and aria-label (frontend rules 3.6.6). Points come straight from the
// snapshot series — never fabricated.
import type { TrendPoint } from '../../../types/api';

/** Width/height of the inline SVG viewBox — coordinates scale to these. */
const VIEW_W = 120;
const VIEW_H = 32;
const PAD = 2;

interface TrendSparklineProps {
  /** Snapshot series ordered by date ascending (backend guarantees order). */
  points: TrendPoint[];
  /** Subfield name for the accessible label. */
  subfieldName: string;
}

export function TrendSparkline({ points, subfieldName }: TrendSparklineProps) {
  if (points.length === 0) {
    return (
      <p data-testid="trend-status" className="text-[11px] text-slate-500">
        no history yet
      </p>
    );
  }

  if (points.length === 1) {
    return (
      <p data-testid="trend-status" className="text-[11px] text-slate-500">
        tracking started {points[0].date}
      </p>
    );
  }

  const activeValues = points.map((p) => p.active);
  const maxValue = Math.max(...activeValues);
  // Guard against a flat all-zero series: give the baseline a fixed height.
  const yFor = (value: number) =>
    maxValue === 0 ? VIEW_H - PAD : VIEW_H - PAD - (value / maxValue) * (VIEW_H - 2 * PAD);
  const xFor = (index: number) => PAD + (index / (points.length - 1)) * (VIEW_W - 2 * PAD);
  const polyline = points
    .map((point, index) => `${xFor(index).toFixed(1)},${yFor(point.active).toFixed(1)}`)
    .join(' ');

  const summary =
    `Active postings trend for ${subfieldName}: ` +
    points.map((p) => `${p.date}: ${p.active}`).join(', ');

  return (
    <svg
      role="img"
      aria-label={summary}
      data-testid="trend-sparkline"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      className="h-8 w-full text-cyan-400"
      preserveAspectRatio="none"
    >
      <title>{summary}</title>
      <polyline
        points={polyline}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
