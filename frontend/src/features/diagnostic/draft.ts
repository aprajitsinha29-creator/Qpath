/**
 * Diagnostic draft persistence (plan 3.5): sessionStorage, not localStorage.
 *
 * A mid-quiz refresh must not lose progress, but the draft is per-tab and
 * ephemeral — the profile identity is the durable part (localStorage).
 */

import type { AnswerIn } from '../../types/api';

const DRAFT_KEY = 'quantum_pathfinder_diagnostic_draft';

/**
 * The backend scores exactly these six subfields (services/quiz_service.py
 * rejects any submission missing one), so they are the slider defaults too:
 * the UI shows 1 for every untouched slider — submitting must never send less
 * than what is shown (regression: empty interests state → 422).
 */
export const DEFAULT_INTERESTS: Record<string, number> = {
  qec: 1,
  hardware: 1,
  software: 1,
  algorithms: 1,
  qml: 1,
  crypto_net: 1,
};

const INTEREST_MIN = 1;
const INTEREST_MAX = 5;

/**
 * Fill missing/incomplete interest entries with the displayed defaults and
 * clamp stored values into the 1–5 slider range, so what is shown is always
 * what gets submitted. Known ids only: older drafts may carry keys the
 * current backend no longer scores, and those would be rejected server-side.
 */
export function normalizeInterests(interests: Record<string, number>): Record<string, number> {
  const normalized: Record<string, number> = {};
  for (const [id, fallback] of Object.entries(DEFAULT_INTERESTS)) {
    const raw = interests[id];
    normalized[id] =
      typeof raw === 'number' && Number.isFinite(raw) && raw >= INTEREST_MIN && raw <= INTEREST_MAX
        ? raw
        : fallback;
  }
  return normalized;
}

/** Everything needed to resume the diagnostic where the user left off. */
export interface DiagnosticDraft {
  /** 0 = interest sliders, 1..n = question n (1-based). */
  step: number;
  interests: Record<string, number>;
  /** question_id -> selected index, or null for "Not sure". */
  answers: Record<string, number | null>;
}

export function emptyDraft(): DiagnosticDraft {
  return { step: 0, interests: normalizeInterests({}), answers: {} };
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
      // A stored draft may predate interest defaults or have lost values;
      // repair it instead of resuming in a state that would fail validation.
      interests: normalizeInterests(parsed.interests ?? {}),
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
 * Drop the draft (after a successful submission, "Start over", or any reset
 * back to a state with no user-entered progress).
 */
export function clearDraft(): void {
  sessionStorage.removeItem(DRAFT_KEY);
}

/**
 * True when the draft holds no user progress: still on the interest step, no
 * answers, and interests equal to the displayed defaults. Pristine drafts are
 * removed from storage rather than saved so "Start over" genuinely clears
 * sessionStorage instead of leaving a replayed default snapshot behind.
 */
export function isPristineDraft(draft: DiagnosticDraft): boolean {
  return (
    draft.step === 0 &&
    Object.keys(draft.answers).length === 0 &&
    JSON.stringify(normalizeInterests(draft.interests)) === JSON.stringify(DEFAULT_INTERESTS)
  );
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
