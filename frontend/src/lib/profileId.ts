/**
 * Anonymous profile UUID manager for localStorage (AGENTS.md 3.10.4).
 *
 * Keeps client state tied to an anonymous identifier without collecting
 * personal identifiable information. `ensureProfileId` also syncs the id with
 * the backend (POST /profiles is idempotent for a client-supplied UUID, so a
 * retry after a lost response is safe).
 */

import { apiClient } from './apiClient';
import type { ProfileResponse } from '../types/api';

const STORAGE_KEY = 'quantum_pathfinder_profile_id';

/**
 * Retrieve the locally stored profile UUID, generating and persisting one if absent.
 */
export function getOrCreateProfileId(): string {
  let profileId = localStorage.getItem(STORAGE_KEY);
  if (!profileId) {
    profileId = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, profileId);
  }
  return profileId;
}

/**
 * Ensure the backend knows this profile: create it when missing (idempotent).
 *
 * Used by the diagnostic before the first submission; a network failure here
 * is not fatal — the assessment submit will create it server-side anyway.
 */
export async function ensureProfileId(): Promise<string> {
  const profileId = getOrCreateProfileId();
  try {
    await apiClient.post<ProfileResponse>('/profiles', { profile_id: profileId });
  } catch {
    // The backend may be unreachable while the UI is viewed offline; the UUID
    // is still valid locally and POST /profiles runs again before submit.
  }
  return profileId;
}

/**
 * Clear the stored anonymous profile identifier.
 */
export function clearProfileId(): void {
  localStorage.removeItem(STORAGE_KEY);
}
