// Renders the per-question feedback list: correct / incorrect / not-sure
// states with expandable explanations. Needs the questions (id -> stem), the
// assessment's per-question feedback, and the user's own selections (the
// backend never reveals them — the client already knows what it submitted).
import { useState } from 'react';
import type { AssessmentResult, QuizQuestion } from '../../../types/api';

interface FeedbackListProps {
  questions: QuizQuestion[];
  result: AssessmentResult;
  /** question_id -> the index the user selected, or null for "Not sure". */
  selectedByQuestion: Record<string, number | null>;
}

type FeedbackState = 'correct' | 'incorrect' | 'not_sure';

function stateOf(
  item: AssessmentResult['per_question'][number],
  selected: number | null | undefined,
): FeedbackState {
  if (item.correct) return 'correct';
  // selected === undefined means the question was never answered at all;
  // the UI treats it like "Not sure" (same honest label, plan 3.5).
  return selected === null || selected === undefined ? 'not_sure' : 'incorrect';
}

const STATE_STYLES: Record<FeedbackState, string> = {
  correct: 'border-emerald-800 bg-emerald-950/30 text-emerald-300',
  incorrect: 'border-rose-800 bg-rose-950/30 text-rose-300',
  not_sure: 'border-amber-800 bg-amber-950/30 text-amber-300',
};

const STATE_LABELS: Record<FeedbackState, string> = {
  correct: 'Correct',
  incorrect: 'Incorrect',
  not_sure: 'Not sure',
};

export function FeedbackList({ questions, result, selectedByQuestion }: FeedbackListProps) {
  const [openId, setOpenId] = useState<string | null>(null);
  const stemById = new Map(questions.map((q) => [q.id, q.stem]));

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">Question feedback</h2>
      <ul className="space-y-2">
        {result.per_question.map((item) => {
          const state = stateOf(item, selectedByQuestion[item.question_id]);
          const isOpen = openId === item.question_id;
          return (
            <li
              key={item.question_id}
              className={`overflow-hidden rounded-lg border ${STATE_STYLES[state]}`}
            >
              <button
                type="button"
                onClick={() => setOpenId(isOpen ? null : item.question_id)}
                aria-expanded={isOpen}
                className="flex w-full items-center justify-between gap-3 p-3 text-left text-sm"
              >
                <span className="flex-1 text-slate-200">
                  {stemById.get(item.question_id) ?? item.question_id}
                </span>
                <span className="shrink-0 text-xs font-semibold uppercase tracking-wide">
                  {STATE_LABELS[state]}
                </span>
              </button>
              {isOpen && (
                <p className="border-t border-slate-800/60 bg-slate-950/40 p-3 text-xs leading-relaxed text-slate-300">
                  {item.explanation || 'No explanation available for this question yet.'}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
