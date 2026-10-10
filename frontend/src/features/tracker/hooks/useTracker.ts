/**
 * TanStack Query hooks for the tracker feature (plan 5.1–5.3).
 *
 * useChosenPath / useSetChosenPath: the tracked path id (server state keyed
 * per profile). useOpportunities: the feed with filters folded into the query
 * key so region/internship changes refetch cleanly. useMarkSeen: POST /seen
 * then refetch the feed (badges clear, plan 5.5). useTrend: the pulse
 * sparkline series (plan 5.4).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../../lib/apiClient';
import type { ChosenPathResponse, OpportunitiesResponse, TrendPoint } from '../../../types/api';
import { getOpportunities, postSeen, putChosenPath } from '../api';

const CHOSEN_PATH_KEY = (profileId: string) => ['chosenPath', profileId] as const;
const OPPORTUNITIES_KEY = (profileId: string, region: string, internship: boolean | null) =>
  ['opportunities', profileId, region, String(internship)] as const;

export function opportunityQueryKey(profileId: string, region: string, internship: boolean | null) {
  return OPPORTUNITIES_KEY(profileId, region, internship);
}

/** Fetch the tracked path id by reading GET /profiles/{id} (Phase 5 field). */
export function useChosenPath(profileId: string) {
  return useQuery<ChosenPathResponse>({
    queryKey: CHOSEN_PATH_KEY(profileId),
    queryFn: async () => {
      // ProfileResponse carries chosen_path_id; project to the pair shape.
      const profile = await apiClient.get<{
        profile_id: string;
        chosen_path_id: string | null;
      }>(`/profiles/${encodeURIComponent(profileId)}`);
      return { profile_id: profile.profile_id, chosen_path_id: profile.chosen_path_id };
    },
    staleTime: 60 * 1000,
  });
}

/** Mutation: PUT chosen-path; updates the cache and the profile query. */
export function useSetChosenPath(profileId: string) {
  const queryClient = useQueryClient();
  return useMutation<ChosenPathResponse, Error, string>({
    mutationFn: (pathId) => putChosenPath(profileId, pathId),
    onSuccess: (data) => {
      queryClient.setQueryData(CHOSEN_PATH_KEY(profileId), data);
      // The nav "Opportunities" gate and others read the profile too.
      queryClient.invalidateQueries({ queryKey: ['profile', profileId] });
    },
  });
}

/** Fetch the matched-opportunities feed with the current filters. */
export function useOpportunities(profileId: string, region: string, internship: boolean | null) {
  return useQuery<OpportunitiesResponse>({
    queryKey: OPPORTUNITIES_KEY(profileId, region, internship),
    queryFn: async () => {
      // Explicit qs path keeps the cache key and the request in lockstep.
      return getOpportunities(profileId, { region, internship, limit: 50, offset: 0 });
    },
    staleTime: 30 * 1000,
  });
}

/** Mutation: POST /seen then refetch the feed so is_new badges clear. */
export function useMarkSeen(profileId: string, region: string, internship: boolean | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => postSeen(profileId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: OPPORTUNITIES_KEY(profileId, region, internship),
      });
      void queryClient.invalidateQueries({ queryKey: ['profile', profileId] });
    },
  });
}

const TREND_KEY = (subfieldId: string, region: string) =>
  ['pulseTrend', subfieldId, region] as const;

/** Fetch the subfield's daily snapshot series for the sparkline (plan 5.4). */
export function useTrend(subfieldId: string, region: string) {
  return useQuery<TrendPoint[]>({
    queryKey: TREND_KEY(subfieldId, region),
    queryFn: () =>
      apiClient.get<TrendPoint[]>(
        `/pulse/${encodeURIComponent(subfieldId)}/trend?region=${encodeURIComponent(region)}`,
      ),
    staleTime: 5 * 60 * 1000,
  });
}

/** Hook key so tests/consumers prime exactly the trend query used here. */
export function trendQueryKey(subfieldId: string, region: string) {
  return TREND_KEY(subfieldId, region);
}
