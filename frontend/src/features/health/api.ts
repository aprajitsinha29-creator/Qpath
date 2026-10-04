/**
 * Health feature API client (AGENTS.md 3.6.2, BUILD_PLAN.md 0.6.4).
 *
 * Wraps GET /api/v1/health to probe service and database connectivity.
 */

import { apiClient } from '../../lib/apiClient';
import type { HealthResponse } from '../../types/api';

/**
 * Fetch health status from the backend API.
 */
export async function getHealth(): Promise<HealthResponse> {
  return apiClient.get<HealthResponse>('/health');
}
