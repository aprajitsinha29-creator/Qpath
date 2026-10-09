/**
 * Paths feature API client (AGENTS.md 3.6.2).
 *
 * Wraps GET /profiles/{id}/paths and POST /profiles/{id}/paths/explanations.
 * Components never call fetch directly; all HTTP goes through apiClient.
 */

import { apiClient } from '../../lib/apiClient';
import type { PathsOut } from '../../types/api';

/**
 * Fetch the six ranked career paths for a profile (requires an assessment).
 * Throws with status 409 and code "assessment_required" if no assessment exists.
 */
export function getRankedPaths(profileId: string): Promise<PathsOut> {
  return apiClient.get<PathsOut>(`/profiles/${encodeURIComponent(profileId)}/paths`);
}

/**
 * Generate (or return cached) explanations for all six ranked paths in one
 * batched Gemini call. Always returns the full PathsOut with explanations
 * populated; falls back to templates silently on LLM failure.
 */
export function requestExplanations(profileId: string): Promise<PathsOut> {
  return apiClient.post<PathsOut>(
    `/profiles/${encodeURIComponent(profileId)}/paths/explanations`,
    {},
  );
}
