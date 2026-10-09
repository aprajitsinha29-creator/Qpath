// Renders the diagnostic results: readiness radar (with interest overlay),
// per-subfield bars, expandable question feedback, retake action. Needs the
// profile's latest assessment (GET /profiles/{id}/assessments/latest) and taxonomy.
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useTaxonomy } from '../features/pulse/hooks/usePulse';
import { FeedbackList } from '../features/diagnostic/components/FeedbackList';
import { ReadinessRadar } from '../features/diagnostic/components/ReadinessRadar';
import { ScoreBars } from '../features/diagnostic/components/ScoreBars';
import { useLatestAssessment, useQuiz } from '../features/diagnostic/hooks/useDiagnostic';
import { getOrCreateProfileId } from '../lib/profileId';
import { loadDraft } from '../features/diagnostic/draft';

export function ResultsPage() {
  const profileId = getOrCreateProfileId();
  const { data: result, isLoading, isError, error } = useLatestAssessment(profileId);
  const quizQuery = useQuiz();
  const taxonomyQuery = useTaxonomy();

  const subfields = useMemo(
    () => (taxonomyQuery.data?.subfields ?? []).filter((s) => s.is_scored),
    [taxonomyQuery.data],
  );
  const questions = useMemo(() => quizQuery.data?.questions ?? [], [quizQuery.data]);

  // The selections the user made are client-side knowledge (the draft keeps
  // them until cleared); a fresh page load after submit may not have them.
  const selectedByQuestion = useMemo(() => loadDraft().answers, []);

  const retake = () => {
    // Back to the diagnostic; the draft was cleared after submit so it starts fresh.
    window.location.href = '/diagnostic';
  };

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading results" className="space-y-3">
        <div className="h-8 w-1/3 animate-pulse rounded bg-slate-800/60" />
        <div className="h-72 animate-pulse rounded-xl bg-slate-800/60" />
      </div>
    );
  }

  if (isError) {
    const status = (error as { status?: number }).status;
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div
          role={status === 404 ? 'status' : 'alert'}
          className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400"
        >
          {status === 404 ? (
            <>
              <p>No diagnostic results yet.</p>
              <Link
                to="/diagnostic"
                className="mt-3 inline-block rounded-md bg-cyan-600 px-4 py-2 font-semibold text-white hover:bg-cyan-500"
              >
                Take the diagnostic
              </Link>
            </>
          ) : (
            <p>
              Could not load your results:{' '}
              {error instanceof Error ? error.message : 'The API request failed.'}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (!result) {
    return null; // unreachable while loading/error handled above
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Your readiness</h1>
          <p className="text-sm text-slate-400">
            Scored from your answers — difficulty-weighted points, no negative marking.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={retake}
            className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-900"
          >
            Retake
          </button>
          <Link
            to="/paths"
            className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500"
          >
            See your paths
          </Link>
          <Link to="/" className="text-sm text-slate-400 underline hover:text-slate-300">
            Market Pulse
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ReadinessRadar subfields={subfields} scores={result.scores} interests={result.interests} />
        <ScoreBars subfields={subfields} scores={result.scores} />
      </div>

      <FeedbackList questions={questions} result={result} selectedByQuestion={selectedByQuestion} />

      {result.weak_concepts.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm">
          <h2 className="font-semibold text-white">Concepts to revisit</h2>
          <p className="mt-1 text-xs text-slate-400">{result.weak_concepts.join(' · ')}</p>
        </div>
      )}
    </div>
  );
}
