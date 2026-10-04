/**
 * Tests for HealthBadge: ok, loading, and error states (BUILD_PLAN.md 0.8).
 *
 * Uses vitest + @testing-library/react. TanStack Query is configured with
 * a fresh QueryClient per test to avoid state leakage.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import * as healthApi from '../api';
import { HealthBadge } from './HealthBadge';

// Build a fresh QueryClient for every test so cache doesn't bleed.
function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe('HealthBadge', () => {
  it('renders "Backend: OK" when health check succeeds', async () => {
    vi.spyOn(healthApi, 'getHealth').mockResolvedValue({
      status: 'ok',
      version: '0.1.0',
      env: 'development',
      db: 'ok',
    });

    render(<HealthBadge />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('status', { name: /backend status ok/i })).toBeInTheDocument();
    });
    expect(screen.getByText('Backend: OK')).toBeInTheDocument();
  });

  it('renders loading state while the query is in-flight', () => {
    vi.spyOn(healthApi, 'getHealth').mockReturnValue(new Promise(() => {}));

    render(<HealthBadge />, { wrapper: makeWrapper() });

    expect(screen.getByRole('status', { name: /checking backend/i })).toBeInTheDocument();
    expect(screen.getByText('Checking backend...')).toBeInTheDocument();
  });

  it('renders "Backend: unreachable" when health check fails', async () => {
    vi.spyOn(healthApi, 'getHealth').mockRejectedValue(new Error('Network error'));

    render(<HealthBadge />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(
        screen.getByRole('status', { name: /backend status unreachable/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Backend: unreachable')).toBeInTheDocument();
  });

  it('renders "Backend: unreachable" when status is error', async () => {
    vi.spyOn(healthApi, 'getHealth').mockResolvedValue({
      status: 'error',
      version: '0.1.0',
      env: 'development',
      db: 'error',
    });

    render(<HealthBadge />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(
        screen.getByRole('status', { name: /backend status unreachable/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Backend: unreachable')).toBeInTheDocument();
  });
});
