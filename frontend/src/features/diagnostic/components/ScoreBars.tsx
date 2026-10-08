// Renders one horizontal readiness bar per scored subfield (text-first
// companion to the radar chart). Needs subfields and the assessment scores.
import type { SubfieldOut } from '../../../types/api';

interface ScoreBarsProps {
  subfields: SubfieldOut[];
  scores: Record<string, number>;
}

// Literal Tailwind classes so the JIT sees every width (AGENTS.md 3.6.6).
const BAR_WIDTHS = [
  'w-0',
  'w-[10%]',
  'w-[20%]',
  'w-[30%]',
  'w-[40%]',
  'w-[50%]',
  'w-[60%]',
  'w-[70%]',
  'w-[80%]',
  'w-[90%]',
  'w-full',
];

function barClass(score: number): string {
  const index = Math.min(10, Math.max(0, Math.round(score / 10)));
  return BAR_WIDTHS[index];
}

function barColor(score: number): string {
  if (score >= 67) return 'bg-emerald-500';
  if (score >= 34) return 'bg-cyan-500';
  return 'bg-amber-500';
}

export function ScoreBars({ subfields, scores }: ScoreBarsProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">Readiness per subfield</h2>
      <ul className="space-y-3">
        {subfields.map((s) => {
          const score = Math.round(scores[s.id] ?? 0);
          return (
            <li key={s.id}>
              <div className="flex items-baseline justify-between text-sm">
                <span className="font-medium text-slate-200">{s.name}</span>
                <span className="font-mono text-slate-400" aria-hidden="true">
                  {score}/100
                </span>
              </div>
              <div
                role="meter"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={score}
                aria-label={`Readiness in ${s.name}: ${score} out of 100`}
                className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-slate-800"
              >
                <div className={`h-full rounded-full ${barClass(score)} ${barColor(score)}`} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
