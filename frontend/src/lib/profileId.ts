/**
 * Anonymous profile UUID manager for localStorage (AGENTS.md 3.10.4).
 *
 * Keeps client state tied to an anonymous identifier without collecting
 * personal identifiable information.
 */

const STORAGE_KEY = 'quantum_pathfinder_profile_id';

/**
 * Retrieve the active profile UUID or create a new random UUID if none exists.
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
 * Clear the stored anonymous profile identifier.
 */
export function clearProfileId(): void {
  localStorage.removeItem(STORAGE_KEY);
}
