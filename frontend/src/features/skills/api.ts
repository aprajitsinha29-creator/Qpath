/**
 * Skills feature API client (AGENTS.md 3.6.2).
 *
 * Wraps GET /skills (vocabulary) and PUT /profiles/{id}/skills (declared
 * skills replacement). Components never call fetch directly; all HTTP goes
 * through apiClient.
 */

import { apiClient } from '../../lib/apiClient';
import type { DeclaredSkillsRequest, ProfileResponse, SkillOut } from '../../types/api';

/** Fetch the full skills vocabulary, sorted by name (bare list per backend schema). */
export function getSkills(): Promise<SkillOut[]> {
  return apiClient.get<SkillOut[]>('/skills');
}

/**
 * Replace the profile's whole declared-skills list.
 * Throws ApiError (status 422, code "invalid_skills") listing unknown ids
 * when any id is not in the vocabulary; nothing is written in that case.
 */
export function putDeclaredSkills(profileId: string, skillIds: string[]): Promise<ProfileResponse> {
  const body: DeclaredSkillsRequest = { skill_ids: skillIds };
  return apiClient.put<ProfileResponse>(`/profiles/${encodeURIComponent(profileId)}/skills`, body);
}
