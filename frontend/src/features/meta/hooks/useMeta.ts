/**
 * TanStack Query hooks for the Method page (Phase 7).
 *
 * useMethodStats: the live-numbers block; static facts that change only when
 * refreshes run, cached 5 minutes. The markdown document is inlined at build
 * time and needs no query.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../../lib/apiClient';
import type { MethodStatsResponse } from '../../../types/api';

/** Fetch the Method-page live numbers from GET /meta/method. */
export function useMethodStats() {
  return useQuery<MethodStatsResponse>({
    queryKey: ['meta', 'method'],
    queryFn: () => apiClient.get<MethodStatsResponse>('/meta/method'),
    staleTime: 5 * 60 * 1000,
  });
}
