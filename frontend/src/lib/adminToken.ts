/**
 * Dev-only admin token storage (AGENTS.md 3.6.7).
 *
 * The token is typed into the UI by the developer and kept in sessionStorage
 * only — never in source, never in localStorage, never sent anywhere except
 * the X-Admin-Token header of admin endpoints.
 */

const STORAGE_KEY = 'qp.admin_token';

/** Read the stored admin token (empty string when absent/unavailable). */
export function getAdminToken(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    // Privacy modes can block storage access; degrade to "not set".
    return '';
  }
}

/** Store the admin token for this tab's session. */
export function setAdminToken(token: string): void {
  try {
    if (token) {
      sessionStorage.setItem(STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage unavailable: the refresh simply won't authenticate.
  }
}

/** Remove the stored admin token. */
export function clearAdminToken(): void {
  setAdminToken('');
}
