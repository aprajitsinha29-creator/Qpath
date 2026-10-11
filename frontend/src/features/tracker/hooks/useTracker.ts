/**
 * TanStack Query hooks for the tracker feature (plan 5.1–5.3).
 *
 * useChosenPath / useSetChosenPath: the tracked path id (server state keyed
 * per profile). useOpportunities: the feed with filters folded into the query
 * key so region/internship changes refetch cleanly. useMarkSeen: POST /seen
 * then refetch the feed (badges clear, plan 5.5). useTrend: the pulse
 * sparkline series (plan 5.4).
 *
 * Cache-invalidation contract: the opportunities feed depends on the tracked
 * path and the seen marker, and its key carries only the filter state. So
 * every mutation that moves those server-side values (chosen path, seen
 * marker, declared skills — the last one from the skills feature) invalidates
 * the WHOLE ['opportunities', profileId] prefix, not just the
 * currently-mounted variant. Prefix invalidation keeps staleTime caching
 * intact (no staleTime=0) while stale filter variants can never be served
 * after a path switch.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../../lib/apiClient';
import type { ChosenPathResponse, OpportunitiesResponse, TrendPoint } from '../../../types/api';
import { getOpportunities, postSeen, putChosenPath } from '../api';

const CHOSEN_PATH_KEY = (profileId: string) => ['chosenPath', profileId] as const;
const OPPORTUNITIES_PREFIX_KEY = (profileId: string) => ['opportunities', profileId] as const;
const OPPORTUNITIES_KEY = (profileId: string, region: string, internship: boolean | null) =>
  ['opportunities', profileId, region, String(internship)] as const;

export function opportunityQueryKey(profileId: string, region: string, internship: boolean | null) {
  return OPPORTUNITIES_KEY(profileId, region, internship);
}

/** Exported so the skills feature invalidates the same prefix shape. */
export function opportunitiesPrefixKey(profileId: string) {
  return OPPORTUNITIES_PREFIX_KEY(profileId);
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
      // The nav gate and the Opportunities subtitle read the profile; the
      // chosen-path id is part of the feed's input set, so every variant of
      // the feed (any region/internship) is stale after a switch.
      void queryClient.invalidateQueries({ queryKey: ['profile', profileId] });
      void queryClient.invalidateQueries({
        queryKey: OPPORTUNITIES_PREFIX_KEY(profileId),
      });
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

/**
 * Mutation: POST /seen then refetch the feed so is_new badges clear.
 * The seen marker is profile-wide, not filter-scoped, so the filter params
 * the hook used to take are gone: the invalidation below covers every
 * region/internship variant of the feed.
 */
export function useMarkSeen(profileId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => postSeen(profileId),
    onSuccess: () => {
      // Every filter variant of the feed shows NEW badges; invalidating only
      // the mounted one left the others stale (seen marker is profile-wide).
      void queryClient.invalidateQueries({
        queryKey: OPPORTUNITIES_PREFIX_KEY(profileId),
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
