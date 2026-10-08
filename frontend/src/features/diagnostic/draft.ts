/**
 * Diagnostic draft persistence (plan 3.5): sessionStorage, not localStorage.
 *
 * A mid-quiz refresh must not lose progress, but the draft is per-tab and
 * ephemeral — the profile identity is the durable part (localStorage).
 */

import type { AnswerIn } from '../../types/api';

const DRAFT_KEY = 'quantum_pathfinder_diagnostic_draft';

/** Everything needed to resume the diagnostic where the user left off. */
export interface DiagnosticDraft {
  /** 0 = interest sliders, 1..n = question n (1-based). */
  step: number;
  interests: Record<string, number>;
  /** question_id -> selected index, or null for "Not sure". */
  answers: Record<string, number | null>;
}

export function emptyDraft(): DiagnosticDraft {
  return { step: 0, interests: {}, answers: {} };
}

/**
 * Load the draft for this tab, or an empty one; malformed drafts are ignored.
 */
export function loadDraft(): DiagnosticDraft {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    if (!raw) {
      return emptyDraft();
    }
    const parsed = JSON.parse(raw) as Partial<DiagnosticDraft>;
    return {
      step: typeof parsed.step === 'number' && parsed.step >= 0 ? parsed.step : 0,
      interests: parsed.interests ?? {},
      answers: parsed.answers ?? {},
    };
  } catch {
    return emptyDraft();
  }
}

/**
 * Persist the draft (call on every change; sessionStorage writes are cheap).
 */
export function saveDraft(draft: DiagnosticDraft): void {
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
}

/**
 * Drop the draft (after a successful submission or an explicit retake).
 */
export function clearDraft(): void {
  sessionStorage.removeItem(DRAFT_KEY);
}

/**
 * Convert the draft answers into the API answer list (insertion order kept).
 */
export function draftToAnswers(answers: Record<string, number | null>): AnswerIn[] {
  return Object.entries(answers).map(([question_id, selected_index]) => ({
    question_id,
    selected_index,
  }));
}
