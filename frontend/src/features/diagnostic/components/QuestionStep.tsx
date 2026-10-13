// Renders one quiz question per screen: progress bar, options as a native
// radio group (keyboard operable), "Not sure" and back/next controls.
// Needs the current question, the selected index (or null), and callbacks.
import type { QuizQuestion } from '../../../types/api';

// Tailwind's JIT needs literal class names in source, so the 20 possible
// progress widths are enumerated here instead of using an inline style
// (AGENTS.md 3.6.6: Tailwind utilities only).
const PROGRESS_WIDTHS = [
  'w-0',
  'w-[5%]',
  'w-[10%]',
  'w-[15%]',
  'w-[20%]',
  'w-[25%]',
  'w-[30%]',
  'w-[35%]',
  'w-[40%]',
  'w-[45%]',
  'w-[50%]',
  'w-[55%]',
  'w-[60%]',
  'w-[65%]',
  'w-[70%]',
  'w-[75%]',
  'w-[80%]',
  'w-[85%]',
  'w-[90%]',
  'w-[95%]',
  'w-full',
];

function progressClass(questionNumber: number, total: number): string {
  const fraction = total > 0 ? Math.round((questionNumber / total) * 20) : 0;
  return PROGRESS_WIDTHS[Math.min(fraction, PROGRESS_WIDTHS.length - 1)];
}

interface QuestionStepProps {
  question: QuizQuestion;
  questionNumber: number;
  totalQuestions: number;
  /** Selected index, null = "Not sure" chosen, undefined = no selection yet. */
  selectedIndex: number | null | undefined;
  onSelect: (selectedIndex: number | null) => void;
  // Going back one step always lands somewhere valid: question 1's Back
  // returns to step 0, which is the interest sliders screen.
  onBack: () => void;
  onNext: () => void;
}

export function QuestionStep({
  question,
  questionNumber,
  totalQuestions,
  selectedIndex,
  onSelect,
  onBack,
  onNext,
}: QuestionStepProps) {
  // Skipping is allowed: unanswered questions score 0 like "Not sure", and the
  // review step warns about them before submission (plan 3.5). "Not sure" IS
  // a selection (null), so it makes the Next button say "Next", not "Skip".
  const answered = selectedIndex !== undefined;
  return (
    <div className="space-y-6">
      {/* Progress bar: text alternative via aria + visible label */}
      <div>
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>
            Question {questionNumber} of {totalQuestions}
          </span>
          <span>Difficulty {question.difficulty}/3</span>
        </div>
        <div
          role="progressbar"
          aria-valuemin={1}
          aria-valuemax={totalQuestions}
          aria-valuenow={questionNumber}
          aria-label={`Question ${questionNumber} of ${totalQuestions}`}
          className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-800"
        >
          <div
            className={`h-full rounded-full bg-cyan-500 transition-all ${progressClass(questionNumber, totalQuestions)}`}
          />
        </div>
      </div>{' '}
      {/* Plain <div>/<header> (not fieldset/legend) so the stem sits inside the
            padded card with the options. A <legend> renders its text outside the
            fieldset border box, which pushes the stem above/outside the card — the
            bug described above. */}
      <div
        className="rounded-xl border border-slate-800 bg-slate-900/50 p-5"
        role="group"
        aria-labelledby={`question-stem-${question.id}`}
      >
        {' '}
        <header id={`question-stem-${question.id}`} className="text-lg font-semibold text-white">
          {' '}
          {question.stem}
        </header>
        <div className="mt-4 space-y-2">
          {question.options.map((option, index) => (
            <label
              key={index}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm transition-colors ${
                selectedIndex === index
                  ? 'border-cyan-600 bg-cyan-950/40 text-slate-100'
                  : 'border-slate-800 bg-slate-900/70 text-slate-300 hover:border-slate-700'
              }`}
            >
              <input
                type="radio"
                name={`question-${question.id}`}
                value={index}
                checked={selectedIndex === index}
                onChange={() => onSelect(index)}
                className="mt-0.5 accent-cyan-500"
              />
              <span>{option}</span>
            </label>
          ))}
          {/* "Not sure" is its own choice (scores 0 without guessing, plan 1.3). */}
          <button
            type="button"
            onClick={() => onSelect(null)}
            aria-pressed={selectedIndex === null}
            className={
              selectedIndex === null
                ? 'w-full rounded-lg border p-3 text-sm font-medium transition-colors border-amber-600 bg-amber-950/40 text-amber-200'
                : 'w-full rounded-lg border p-3 text-sm font-medium transition-colors border-slate-800 bg-slate-900/70 text-slate-400 hover:border-slate-700'
            }
          >
            Not sure
          </button>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-900"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onNext}
          aria-label={answered ? 'Next question' : 'Skip question'}
          className="rounded-md bg-cyan-600 px-5 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
