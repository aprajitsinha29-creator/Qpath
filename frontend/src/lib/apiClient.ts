/**
 * Central HTTP client for the QPath API (AGENTS.md 3.6.2).
 *
 * All frontend requests go through this module. Backend error payloads
 * ({"error": {"code", "message"}}) are normalized into thrown ApiError instances.
 */

import type { ApiErrorResponse } from '../types/api';

const DEFAULT_BASE_URL = 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  /**
   * Domain-aware HTTP error thrown by the API client.
   *
   * @param message Human-readable error message.
   * @param code Stable snake_case error code from the backend.
   * @param status HTTP response status code.
   */
  constructor(message: string, code = 'unknown_error', status = 0) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

/**
 * Returns the configured base URL, stripped of trailing slashes.
 */
export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const url = envUrl && envUrl.trim().length > 0 ? envUrl.trim() : DEFAULT_BASE_URL;
  return url.replace(/\/+$/, '');
}

/**
 * Normalizes HTTP failure responses into typed ApiError exceptions.
 */
async function handleResponseError(response: Response): Promise<never> {
  let code = 'http_error';
  let message = `Request failed with status ${response.status}`;

  try {
    const data = (await response.json()) as ApiErrorResponse | Record<string, unknown>;
    if ('error' in data && data.error && typeof data.error === 'object') {
      const err = data.error as { code?: string; message?: string };
      if (typeof err.code === 'string') {
        code = err.code;
      }
      if (typeof err.message === 'string') {
        message = err.message;
      }
    }
  } catch {
    // Non-JSON response body; keep default message
  }

  throw new ApiError(message, code, response.status);
}

/**
 * Dispatches an HTTP request and parses JSON results.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${baseUrl}${cleanPath}`;

  const headers = new Headers(init?.headers);
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, { ...init, headers });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Network request failed';
    throw new ApiError(errorMsg, 'network_error', 0);
  }

  if (!response.ok) {
    await handleResponseError(response);
  }

  return (await response.json()) as T;
}

export const apiClient = {
  /**
   * Execute an HTTP GET request.
   */
  get<T>(path: string, init?: Omit<RequestInit, 'method'>): Promise<T> {
    return request<T>(path, { ...init, method: 'GET' });
  },

  /**
   * Execute an HTTP POST request with JSON payload.
   */
  post<T>(path: string, body?: unknown, init?: Omit<RequestInit, 'method' | 'body'>): Promise<T> {
    const headers = new Headers(init?.headers);
    if (body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    return request<T>(path, {
      ...init,
      headers,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  /**
   * Execute an HTTP PUT request with JSON payload.
   */
  put<T>(path: string, body?: unknown, init?: Omit<RequestInit, 'method' | 'body'>): Promise<T> {
    const headers = new Headers(init?.headers);
    if (body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    return request<T>(path, {
      ...init,
      headers,
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
};
