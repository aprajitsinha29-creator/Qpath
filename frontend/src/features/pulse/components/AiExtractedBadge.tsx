// Badge with tooltip: "AI-extracted from posting text". Renders inline next to
// AI-derived skill/theme blocks (AGENTS.md 3.6.6).
import type { ReactNode } from 'react';

interface AiExtractedBadgeProps {
  /** Extra class applied to the wrapper span. */
  className?: string;
  children?: ReactNode;
}

/** Small badge that signals content was extracted by the LLM. */
export function AiExtractedBadge({ className = '', children }: AiExtractedBadgeProps) {
  return (
    <span
      title="AI-extracted from posting text"
      aria-label="AI-extracted from posting text"
      className={`inline-flex items-center gap-1 rounded border border-purple-800/60 bg-purple-950/40 px-1.5 py-0.5 text-[10px] font-medium text-purple-300 ${className}`}
    >
      <span aria-hidden="true">✦</span>
      {children ?? 'AI-extracted'}
    </span>
  );
}
