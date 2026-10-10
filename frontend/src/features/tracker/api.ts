/**
 * Tracker feature API client (AGENTS.md 3.6.2).
 *
 * Wraps PUT /profiles/{id}/chosen-path, POST /profiles/{id}/seen, and
 * GET /profiles/{id}/opportunities (plan 5.1–5.3). Components never call
 * fetch directly; all HTTP goes through apiClient.
 */

import { apiClient } from '../../lib/apiClient';
import type {
  ChosenPathRequest,
  ChosenPathResponse,
  OpportunitiesResponse,
  SeenResponse,
} from '../../types/api';

/** Track (or switch) the profile's career path (plan 5.1). */
export function putChosenPath(profileId: string, pathId: string): Promise<ChosenPathResponse> {
  const body: ChosenPathRequest = { path_id: pathId };
  return apiClient.put<ChosenPathResponse>(
    `/profiles/${encodeURIComponent(profileId)}/chosen-path`,
    body,
  );
}

/** Mark the feed as seen (explicit; GET opportunities never does this). */
export function postSeen(profileId: string): Promise<SeenResponse> {
  return apiClient.post<SeenResponse>(`/profiles/${encodeURIComponent(profileId)}/seen`, {});
}

/**
 * Fetch the opportunities feed. Throws ApiError with status 409 and code
 * "path_required" when no path is tracked — callers redirect to /paths.
 */
export function getOpportunities(
  profileId: string,
  params: { region?: string; internship?: boolean | null; limit?: number; offset?: number } = {},
): Promise<OpportunitiesResponse> {
  const search = new URLSearchParams();
  if (params.region) {
    search.set('region', params.region);
  }
  if (params.internship === true) {
    search.set('internship', 'true');
  } else if (params.internship === false) {
    search.set('internship', 'false');
  }
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    search.set('offset', String(params.offset));
  }
  const qs = search.toString();
  return apiClient.get<OpportunitiesResponse>(
    `/profiles/${encodeURIComponent(profileId)}/opportunities${qs ? `?${qs}` : ''}`,
  );
}
