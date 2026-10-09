/**
 * TanStack Query hooks for the diagnostic feature (AGENTS.md 3.6.3).
 *
 * Server state lives here; components stay presentational. The draft is NOT
 * server state — it lives in sessionStorage via features/diagnostic/draft.ts.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AssessmentRequest } from '../../../types/api';
import { getLatestAssessment, getQuiz, submitAssessment } from '../api';
import { getOrCreateProfileId } from '../../../lib/profileId';

/** Query hook: the servable quiz questions. */
export function useQuiz() {
  return useQuery({ queryKey: ['quiz'], queryFn: getQuiz });
}

/** Query hook: the profile's latest assessment (null when none exists yet). */
export function useLatestAssessment(profileId: string | null) {
  return useQuery({
    queryKey: ['diagnostic', 'latest', profileId],
    queryFn: () => getLatestAssessment(profileId as string),
    enabled: profileId !== null,
    retry: (failureCount, error) => {
      // A 404 ("no assessments yet") is an expected state, not a failure.
      const status = (error as { status?: number }).status;
      return status !== 404 && failureCount < 2;
    },
  });
}

/**
 * Mutation hook: submit the diagnostic; invalidates the latest-assessment
 * cache so the results page shows the fresh score.
 */
export function useSubmitAssessment(profileId?: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssessmentRequest) => {
      const targetProfileId = profileId ?? getOrCreateProfileId();
      return submitAssessment(targetProfileId, payload);
    },
    onSuccess: () => {
      const targetProfileId = profileId ?? getOrCreateProfileId();
      void queryClient.invalidateQueries({
        queryKey: ['diagnostic', 'latest', targetProfileId],
      });
    },
  });
}
