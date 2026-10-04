/**
 * TypeScript mirror of backend API schemas (AGENTS.md 3.6.1).
 *
 * All request/response contracts between FastAPI (/api/v1) and the React
 * client are declared here.
 */

export interface HealthResponse {
  status: 'ok' | 'error';
  version: string;
  env: string;
  db: 'ok' | 'error';
}

export interface ApiErrorDetail {
  code: string;
  message: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}
