/**
 * TanStack Query hooks for the pulse feature (AGENTS.md 3.6.3).
 *
 * Server state lives here; components stay presentational. Query keys are
 * hierarchical so region changes refetch without stale cache collisions.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getPulseCards,
  getPostings,
  getSerpApiActivity,
  getSubfieldDetail,
  getTaxonomy,
  refreshJobs,
} from '../api';
import type { PulseRegion, RefreshJobsRequest } from '../../../types/api';

/** Query hook: the six pulse cards for a region. */
export function usePulseCards(region: PulseRegion) {
  return useQuery({
    queryKey: ['pulse', 'cards', region],
    queryFn: () => getPulseCards(region),
  });
}

/** Query hook: full subfield detail including skills, mix, themes, postings (Phase 2). */
export function useSubfieldDetail(subfieldId: string, region: PulseRegion) {
  return useQuery({
    queryKey: ['pulse', 'detail', subfieldId, region],
    queryFn: () => getSubfieldDetail(subfieldId, region),
  });
}

/** Query hook: one page of postings for a subfield. */
export function usePostings(
  subfieldId: string,
  options: { region: PulseRegion; internship?: boolean; limit?: number; offset?: number },
) {
  return useQuery({
    queryKey: ['pulse', 'postings', subfieldId, options],
    queryFn: () => getPostings(subfieldId, options),
    // Accordion content is transient; avoid refetch storms on re-expand.
    staleTime: 30_000,
  });
}

/** Query hook: SerpApi activity panel data. */
export function useSerpApiActivity() {
  return useQuery({
    queryKey: ['meta', 'serpapi-activity'],
    queryFn: getSerpApiActivity,
  });
}

/** Query hook: the reference taxonomy (subfields for the region toggle labels). */
export function useTaxonomy() {
  return useQuery({
    queryKey: ['taxonomy'],
    queryFn: getTaxonomy,
    // Reference data only changes when the app re-seeds; cache for the session.
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Mutation hook: run an admin jobs refresh.
 *
 * On success the pulse/meta caches are invalidated so cards and the activity
 * panel reflect the new ingestion immediately.
 */
export function useRefreshJobs() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: RefreshJobsRequest) => refreshJobs(request),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['pulse'] });
      void queryClient.invalidateQueries({ queryKey: ['meta', 'serpapi-activity'] });
    },
  });
}
