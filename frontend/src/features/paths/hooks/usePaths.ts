/**
 * TanStack Query hooks for the paths feature (plan 4.6).
 *
 * usePaths: fetches ranked paths; staleTime=5 min (scoring is deterministic
 * for the same assessment). useRequestExplanations: mutation that triggers
 * batched Gemini generation; updates the paths cache on success.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { PathsOut } from '../../../types/api';
import { getRankedPaths, requestExplanations } from '../api';

const PATHS_KEY = (profileId: string) => ['paths', profileId] as const;

/** Fetch ranked paths for this profile (requires assessment; 409 otherwise). */
export function usePaths(profileId: string) {
  return useQuery<PathsOut, { status?: number; message?: string }>({
    queryKey: PATHS_KEY(profileId),
    queryFn: () => getRankedPaths(profileId),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

/**
 * Mutation to request batched explanations for all six paths.
 * On success the paths cache is replaced with the updated response that
 * includes the explanations.
 */
export function useRequestExplanations(profileId: string) {
  const queryClient = useQueryClient();
  return useMutation<PathsOut, Error>({
    mutationFn: () => requestExplanations(profileId),
    onSuccess: (data) => {
      queryClient.setQueryData(PATHS_KEY(profileId), data);
    },
  });
}
