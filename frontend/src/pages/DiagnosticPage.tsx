// Renders the orientation diagnostic stepper: interest sliders -> 18 questions
// (one per screen) -> confirm -> submit. Draft answers persist in sessionStorage
// so a refresh keeps progress (plan 3.5). Needs GET /quiz and the profile UUID.
import { useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { InterestStep } from '../features/diagnostic/components/InterestStep';
import { QuestionStep } from '../features/diagnostic/components/QuestionStep';
import {
  clearDraft,
  draftToAnswers,
  emptyDraft,
  isPristineDraft,
  loadDraft,
  saveDraft,
  type DiagnosticDraft,
} from '../features/diagnostic/draft';
import { useQuiz, useSubmitAssessment } from '../features/diagnostic/hooks/useDiagnostic';
import { ensureProfileId } from '../lib/profileId';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useTaxonomy } from '../features/pulse/hooks/usePulse';
import { ApiError } from '../lib/apiClient';

export function DiagnosticPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuiz();

  // The draft is loaded once per mount; every change writes it straight back.
  // Pristine state ("Start over", first visit) clears storage instead so the
  // tab draft genuinely disappears when there is no progress to keep.
  const [draft, setDraft] = useState<DiagnosticDraft>(() => loadDraft());
  useEffect(() => {
    if (isPristineDraft(draft)) {
      clearDraft();
    } else {
      saveDraft(draft);
    }
  }, [draft]);

  const [confirming, setConfirming] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  // Set when the backend's 422 points at the interests payload; drives the
  // "Edit interests" button on the review error panel.
  const [interestError, setInterestError] = useState(false);

  const questions = useMemo(() => data?.questions ?? [], [data]);

  const submitMutation = useSubmitAssessment(null); // profile resolved at submit time

  const totalSteps = questions.length + 1; // interests + questions
  const isQuestionStep = draft.step > 0 && draft.step <= questions.length;
  const isReviewStep = draft.step === totalSteps;

  // Taxonomy for subfield names: fetched lazily via the same query the pulse
  // page uses, so the diagnostic works standalone too.
  const taxonomyQuery = useTaxonomy();
  const subfields = useMemo(
    () => (taxonomyQuery.data?.subfields ?? []).filter((s) => s.is_scored),
    [taxonomyQuery.data],
  );

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading diagnostic" className="space-y-3">
        <div className="h-8 w-1/3 animate-pulse rounded bg-slate-800/60" />
        <div className="h-64 animate-pulse rounded-xl bg-slate-800/60" />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-xl border border-rose-900/60 bg-rose-950/40 p-6 text-sm text-rose-200"
      >
        <h2 className="font-semibold">Could not load the diagnostic</h2>
        <p className="mt-1 text-xs">
          {error instanceof Error ? error.message : 'The API request failed.'} Is the backend
          running?
        </p>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400">
        The diagnostic is not available yet — the question bank is empty. Check back soon.
      </div>
    );
  }

  const startSubmit = async () => {
    setConfirming(false);
    setSubmitError(null);
    setInterestError(false);
    try {
      await ensureProfileId();
      const result = await submitMutation.mutateAsync({
        interests: draft.interests,
        answers: draftToAnswers(draft.answers),
      });
      clearDraft();
      await queryClient.invalidateQueries({ queryKey: ['diagnostic'] });
      navigate(`/diagnostic/results?assessment=${result.assessment_id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && /interest/i.test(err.message)) {
        // Backend interest validation failed (should not happen since the
        // defaults are always submitted); offer a fix instead of raw subfield ids.
        setSubmitError(
          'There was a problem with your interest levels. Please review the sliders — each area needs a value from 1 to 5.',
        );
        setInterestError(true);
      } else {
        setSubmitError(err instanceof Error ? err.message : 'Submitting the diagnostic failed.');
      }
    }
  };

  // Only questions with no selection at all count as unanswered: "Not sure"
  // (null) is a deliberate choice that scores 0, not a gap.
  const unansweredCount = questions.filter((q) => draft.answers[q.id] === undefined).length;

  /** Clears the tab draft entirely and returns to the interest sliders. */
  const startOver = () => {
    clearDraft();
    setConfirming(false);
    setSubmitError(null);
    setInterestError(false);
    setDraft(emptyDraft());
  };
  const redirectNotice = (location.state as { message?: string } | null)?.message;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {redirectNotice && (
        <div
          role="status"
          className="rounded-xl border border-cyan-800/80 bg-cyan-950/60 p-4 text-sm text-cyan-200 shadow-md"
        >
          <div className="flex items-start gap-2.5">
            <span className="text-lg">ℹ️</span>
            <div>
              <p className="font-semibold text-white">Diagnostic required first</p>
              <p className="mt-0.5 text-xs text-cyan-300/90">{redirectNotice}</p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight text-white">Orientation diagnostic</h1>
        <p className="text-sm text-slate-400">
          Set your interests, answer {questions.length} questions (one per screen, "Not sure" is
          always available), and see your readiness per subfield.
        </p>
      </div>

      {isQuestionStep && questions[draft.step - 1] && (
        <QuestionStep
          question={questions[draft.step - 1]}
          questionNumber={draft.step}
          totalQuestions={questions.length}
          selectedIndex={draft.answers[questions[draft.step - 1].id]}
          onSelect={(selectedIndex) =>
            setDraft((d) => ({
              ...d,
              answers: { ...d.answers, [questions[draft.step - 1].id]: selectedIndex },
            }))
          }
          onBack={() => setDraft((d) => ({ ...d, step: d.step - 1 }))}
          onNext={() => setDraft((d) => ({ ...d, step: d.step + 1 }))}
        />
      )}

      {draft.step === 0 && (
        <div className="space-y-4">
          <InterestStep
            subfields={subfields}
            interests={draft.interests}
            onChange={(subfieldId, value) =>
              setDraft((d) => ({ ...d, interests: { ...d.interests, [subfieldId]: value } }))
            }
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setDraft((d) => ({ ...d, step: 1 }))}
              className="rounded-md bg-cyan-600 px-5 py-2 text-sm font-semibold text-white hover:bg-cyan-500"
            >
              Start questions
            </button>
          </div>
        </div>
      )}

      {isReviewStep && (
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/50 p-6">
          <h2 className="text-lg font-semibold text-white">Ready to submit?</h2>
          {unansweredCount > 0 && (
            <p className="text-sm text-amber-300">
              {`${unansweredCount} question(s) with no answer selected`} — they will score 0 (same
              as "Not sure").
            </p>
          )}
          {submitError && (
            <div
              role="alert"
              className="rounded-lg border border-rose-900/60 bg-rose-950/40 p-3 text-sm text-rose-200"
            >
              <p>{submitError}</p>
              {interestError && (
                <button
                  type="button"
                  onClick={() => setDraft((d) => ({ ...d, step: 0 }))}
                  className="mt-2 rounded-md bg-rose-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700"
                >
                  Edit interests
                </button>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setDraft((d) => ({ ...d, step: 0 }))}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-900"
              >
                Edit interests
              </button>
              <button
                type="button"
                onClick={() => setDraft((d) => ({ ...d, step: questions.length }))}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-900"
              >
                Back to questions
              </button>
              <button
                type="button"
                onClick={startOver}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-900"
              >
                Start over
              </button>
            </div>
            <div className="flex items-center gap-3">
              {!confirming ? (
                <button
                  type="button"
                  onClick={() => setConfirming(true)}
                  className="rounded-md bg-cyan-600 px-5 py-2 text-sm font-semibold text-white hover:bg-cyan-500"
                >
                  Review submission
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => setConfirming(false)}
                    className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300"
                  >
                    Not yet
                  </button>
                  <button
                    type="button"
                    onClick={startSubmit}
                    disabled={submitMutation.isPending}
                    className="rounded-md bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {submitMutation.isPending ? 'Scoring…' : 'Yes, submit'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <p className="text-center text-xs text-slate-500">
        Your answers are stored against an anonymous profile —{' '}
        <Link to="/method" className="underline hover:text-slate-400">
          how this works
        </Link>
      </p>
    </div>
  );
}
