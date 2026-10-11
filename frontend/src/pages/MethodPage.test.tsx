// MethodPage tests (Phase 7): verbatim document sections, the Live numbers
// block in loading / error / loaded / empty states, and the header comment
// contract (no "placeholder" wording, no unfilled [FILL markers anywhere).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MethodStatsResponse } from '../types/api';

const mockUseMethodStats = vi.fn();
vi.mock('../features/meta/hooks/useMeta', () => ({
  useMethodStats: (...args: unknown[]) => mockUseMethodStats(...args),
}));

import { MethodPage } from './MethodPage';
import { DATA_AND_METHOD_SECTIONS } from '../features/meta/components/MethodDoc';

const EMPTY_STATS: MethodStatsResponse = {
  serpapi_calls: {},
  postings_total: 0,
  postings_active: 0,
  extraction_done: 0,
  themes_count: 0,
  last_jobs_refresh: null,
  last_scholar_refresh: null,
};

const POPULATED_STATS: MethodStatsResponse = {
  serpapi_calls: {
    google_jobs: { live: 5, fixture: 120 },
    google_scholar: { live: 0, fixture: 60 },
  },
  postings_total: 40,
  postings_active: 33,
  extraction_done: 30,
  themes_count: 12,
  last_jobs_refresh: '2026-10-10T03:05:00',
  last_scholar_refresh: '2026-10-06T05:02:00',
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MethodPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default: loaded-but-empty stats (fresh instance) — individual tests
  // override for loading/error/populated states.
  mockUseMethodStats.mockReturnValue({
    data: EMPTY_STATS,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
});

describe('MethodPage', () => {
  it('test_method_page_renders_document_sections_verbatim', () => {
    renderPage();
    // Every markdown section heading and bullet appears word for word.
    for (const section of DATA_AND_METHOD_SECTIONS) {
      expect(screen.getByRole('heading', { name: section.title })).toBeInTheDocument();
      for (const paragraph of section.paragraphs) {
        expect(screen.getByText(paragraph)).toBeInTheDocument();
      }
      for (const bullet of section.bullets ?? []) {
        expect(screen.getByText(bullet)).toBeInTheDocument();
      }
    }
  });

  it('test_method_page_has_no_fill_markers', () => {
    renderPage();
    // [FILL: ...] markers must never appear: the copy is filled with the real
    // numbers from docs/DATA_AND_METHOD.md (M-10 spot check, quiz check).
    for (const text of DATA_AND_METHOD_SECTIONS.flatMap((s) => [
      ...s.paragraphs,
      ...(s.bullets ?? []),
    ])) {
      expect(text).not.toContain('[FILL');
    }
    expect(screen.queryByText(/\[FILL:/)).not.toBeInTheDocument();
  });

  it('test_method_page_is_not_a_placeholder', () => {
    renderPage();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
    // The live block exists and carries no placeholder wording.
    expect(screen.getByTestId('live-numbers')).not.toHaveTextContent('placeholder');
  });

  it('test_live_numbers_shows_engine_split_and_stats', () => {
    mockUseMethodStats.mockReturnValue({
      data: POPULATED_STATS,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();
    const block = screen.getByTestId('live-numbers');
    expect(block).toHaveTextContent(
      /google_jobs — 5 live calls, 120 offline \(recorded fixtures\)/,
    );
    expect(block).toHaveTextContent(
      /google_scholar — 0 live calls, 60 offline \(recorded fixtures\)/,
    );
    expect(block).toHaveTextContent('Postings captured');
    expect(block).toHaveTextContent('75%'); // 30/40 extraction coverage
    expect(block).toHaveTextContent(/Last jobs refresh/);
  });

  it('test_live_numbers_empty_state_when_nothing_logged', () => {
    mockUseMethodStats.mockReturnValue({
      data: EMPTY_STATS,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByText(/No SerpApi calls logged yet/)).toBeInTheDocument();
    // Both refresh stats show their honest "never" state.
    expect(screen.getAllByText('never')).toHaveLength(2);
  });

  it('test_live_numbers_loading_state', () => {
    mockUseMethodStats.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole('status', { name: /loading live numbers/i })).toBeInTheDocument();
  });

  it('test_live_numbers_error_state_with_retry', async () => {
    const refetch = vi.fn();
    mockUseMethodStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    });
    renderPage();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    screen.getByRole('button', { name: /retry/i }).click();
    await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1));
  });
});
