// ResearchFocus: renders a strip of 1–5 research themes, each with an
// expandable list of linked papers. Needs a ThemeOut[] from the detail API.
import { useState } from 'react';
import type { ThemeOut } from '../../../types/api';
import { AiExtractedBadge } from './AiExtractedBadge';

interface ResearchFocusProps {
  themes: ThemeOut[];
}

/** Renders qualitative research themes drawn from Scholar papers. */
export function ResearchFocus({ themes }: ResearchFocusProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (themes.length === 0) {
    return (
      <section aria-label="Research focus">
        <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
          Research focus
        </h4>
        <p className="text-xs italic text-slate-500">
          No research themes yet — run a Scholar refresh to populate this.
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Research focus">
      <div className="mb-2 flex items-center gap-2">
        <h4 className="text-xs font-medium uppercase tracking-wide text-slate-400">
          Research focus
        </h4>
        <AiExtractedBadge />
      </div>

      <ul className="space-y-2">
        {themes.map((theme, idx) => {
          const isExpanded = expandedIndex === idx;
          return (
            <li key={idx} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-slate-200">{theme.label}</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{theme.summary}</p>
                </div>
                {theme.papers.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                    aria-expanded={isExpanded}
                    aria-controls={`theme-papers-${idx}`}
                    className="shrink-0 rounded border border-slate-700 px-2 py-0.5 text-[11px] text-slate-400 transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  >
                    {isExpanded
                      ? 'Hide papers'
                      : `${theme.papers.length} paper${theme.papers.length > 1 ? 's' : ''}`}
                  </button>
                )}
              </div>

              {isExpanded && theme.papers.length > 0 && (
                <ul
                  id={`theme-papers-${idx}`}
                  className="mt-2 space-y-1 border-t border-slate-800 pt-2"
                  aria-label={`Papers for theme ${theme.label}`}
                >
                  {theme.papers.map((paper) =>
                    paper.link ? (
                      <li key={paper.id}>
                        <a
                          href={paper.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-cyan-400 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-cyan-500"
                        >
                          {paper.title}
                        </a>
                      </li>
                    ) : (
                      <li key={paper.id} className="text-xs text-slate-400">
                        {paper.title}
                      </li>
                    ),
                  )}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
