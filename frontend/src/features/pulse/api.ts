/**
 * Pulse feature API client (AGENTS.md 3.6.2).
 *
 * Wraps the Phase 1 & 2 pulse/taxonomy/meta endpoints; components never call
 * fetch directly. All types come from the shared backend mirror.
 */

import { apiClient } from '../../lib/apiClient';
import { getAdminToken } from '../../lib/adminToken';
import type {
  PulseCard,
  PulseRegion,
  PostingListResponse,
  RefreshJobsRequest,
  RefreshSummary,
  SerpApiActivity,
  SubfieldDetail,
  TaxonomyResponse,
} from '../../types/api';

/** Fetch the six pulse cards for a region. */
export function getPulseCards(region: PulseRegion): Promise<PulseCard[]> {
  return apiClient.get<PulseCard[]>(`/pulse?region=${encodeURIComponent(region)}`);
}

/** Fetch full detail for one subfield (Phase 2). */
export function getSubfieldDetail(
  subfieldId: string,
  region: PulseRegion,
): Promise<SubfieldDetail> {
  return apiClient.get<SubfieldDetail>(
    `/pulse/${encodeURIComponent(subfieldId)}?region=${encodeURIComponent(region)}`,
  );
}

/** Fetch one page of postings for a subfield (both query tiers). */
export function getPostings(
  subfieldId: string,
  options: { region: PulseRegion; internship?: boolean; limit?: number; offset?: number },
): Promise<PostingListResponse> {
  const params = new URLSearchParams({ region: options.region });
  if (options.internship !== undefined) {
    params.set('internship', String(options.internship));
  }
  if (options.limit !== undefined) {
    params.set('limit', String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set('offset', String(options.offset));
  }
  return apiClient.get<PostingListResponse>(
    `/pulse/${encodeURIComponent(subfieldId)}/postings?${params.toString()}`,
  );
}

/** Fetch the reference taxonomy (subfields, concepts, career paths). */
export function getTaxonomy(): Promise<TaxonomyResponse> {
  return apiClient.get<TaxonomyResponse>('/taxonomy');
}

/** Fetch the SerpApi activity panel data (mode, cap usage, recent calls). */
export function getSerpApiActivity(): Promise<SerpApiActivity> {
  return apiClient.get<SerpApiActivity>('/meta/serpapi-activity');
}

/**
 * Trigger an admin jobs refresh.
 *
 * Sends the dev-only admin token from sessionStorage as X-Admin-Token; the
 * token never lives in source control (AGENTS.md 3.6.7, 3.10).
 */
export function refreshJobs(request: RefreshJobsRequest): Promise<RefreshSummary> {
  return apiClient.post<RefreshSummary>('/admin/refresh/jobs', request, {
    headers: { 'X-Admin-Token': getAdminToken() },
  });
}
