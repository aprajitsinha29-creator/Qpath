// Renders horizontal skill-frequency bars for a list of SkillShare items.
// Shows a text fallback when no skills have been extracted yet.
// Needs a SkillShare[] from the pulse detail or card payload.
import type { SkillShare } from '../../../types/api';
import { AiExtractedBadge } from './AiExtractedBadge';

interface SkillBarsProps {
  skills: SkillShare[];
  /** Show an extraction-coverage note when < 100%. Omit to hide. */
  extractionCoverage?: number;
}

/** Renders a labelled bar chart of skill frequency shares. */
export function SkillBars({ skills, extractionCoverage }: SkillBarsProps) {
  if (skills.length === 0) {
    return (
      <p className="text-xs italic text-slate-500">
        No skills extracted yet — run extraction to populate this.
      </p>
    );
  }

  return (
    <section aria-label="Top skills">
      <div className="mb-1 flex items-center gap-2">
        <h4 className="text-xs font-medium uppercase tracking-wide text-slate-400">Top skills</h4>
        <AiExtractedBadge />
      </div>

      {/* Screen-reader alternative: a plain list of skill shares */}
      <ul className="space-y-1.5" aria-label="Skill shares list">
        {skills.map((s) => (
          <li key={s.skill_id}>
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="truncate text-slate-200">{s.name}</span>
              <span className="shrink-0 tabular-nums text-slate-400">
                {Math.round(s.share * 100)}%
              </span>
            </div>
            <div
              className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800"
              role="presentation"
            >
              <div
                className="h-full rounded-full bg-cyan-500"
                style={{ width: `${Math.round(s.share * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>

      {extractionCoverage !== undefined && extractionCoverage < 1 && (
        <p className="mt-1.5 text-[11px] text-slate-500">
          Coverage: {Math.round(extractionCoverage * 100)}% of postings extracted — shares are
          estimates.
        </p>
      )}
    </section>
  );
}
