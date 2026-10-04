/**
 * Tests for the central API client (BUILD_PLAN.md 0.8).
 *
 * Uses vitest with global `fetch` mocked via vi.stubGlobal so no real
 * HTTP requests are made.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiClient } from './apiClient';

// Build a minimal Response-like object
function makeResponse(status: number, body: unknown, ok?: boolean): Response {
  const json = JSON.stringify(body);
  return {
    ok: ok ?? (status >= 200 && status < 300),
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(json),
  } as unknown as Response;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('apiClient.get', () => {
  it('returns parsed JSON on a 200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(200, { status: 'ok' })));

    const result = await apiClient.get<{ status: string }>('/health');

    expect(result).toEqual({ status: 'ok' });
  });

  it('throws ApiError with backend code and message on an error response', async () => {
    const errBody = { error: { code: 'not_found', message: 'Resource missing' } };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(404, errBody, false)));

    await expect(apiClient.get('/anything')).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.code === 'not_found' && e.status === 404,
    );
  });

  it('throws ApiError with network_error code when fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(apiClient.get('/health')).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.code === 'network_error' && e.status === 0,
    );
  });
});

describe('apiClient.post', () => {
  it('sets Content-Type and sends the body as JSON', async () => {
    const mockFetch = vi.fn().mockResolvedValue(makeResponse(200, { ok: true }));
    vi.stubGlobal('fetch', mockFetch);

    await apiClient.post('/endpoint', { key: 'value' });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get('content-type')).toBe('application/json');
    expect(init.body).toBe('{"key":"value"}');
    expect(init.method).toBe('POST');
  });
});
