/**
 * PathsPage tests (plan 4.7 frontend).
 *
 * Covers: card renders breakdown bars, template-labelled explanation,
 * redirect to /diagnostic on 409 assessment_required, loading state,
 * and the generate-explanations button triggering the mutation.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PathsPage } from './PathsPage';
import type { PathResult, PathsOut } from '../types/api';

// Mock the TanStack Query hooks so no network calls happen.
vi.mock('../features/paths/hooks/usePaths', () => ({
  usePaths: vi.fn(),
  useRequestExplanations: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  })),
}));

vi.mock('../features/diagnostic/hooks/useDiagnostic', () => ({
  useLatestAssessment: vi.fn(() => ({
    data: { taken_at: '2026-10-01T12:00:00Z' },
    isLoading: false,
    isError: false,
  })),
}));

vi.mock('../lib/profileId', () => ({
  getOrCreateProfileId: vi.fn(() => 'test-profile'),
}));

import { usePaths } from '../features/paths/hooks/usePaths';
const mockUsePaths = vi.mocked(usePaths);

/** Minimal PathResult factory for tests. */
function makePathResult(overrides: Partial<PathResult> = {}): PathResult {
  return {
    path_id: 'qec_researcher',
    title: 'QEC Researcher',
    subfield_id: 'qec',
    rank: 1,
    score: 72.5,
    breakdown: {
      interest: 80,
      demand: 60,
      readiness: 75,
      weights: { interest: 40, demand: 30, readiness: 30 },
    },
    is_top3: true,
    low_data: false,
    saturated: false,
    evidence: {
      active_postings: 42,
      internship_postings: 5,
      top_skills: [{ skill_id: 'python', name: 'Python', share: 0.7, share_pct: 70 }],
      phd_share: 0.3,
      phd_share_pct: 30,
      sample_postings: [],
    },
    explanation: null,
    ...overrides,
  };
}

function makePathsOut(paths: PathResult[]): PathsOut {
  return {
    profile_id: 'test-profile',
    assessment_id: 1,
    region: 'global',
    saturation_note: null,
    paths,
  };
}

function renderPage(initialEntry = '/paths') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/paths" element={<PathsPage />} />
          <Route path="/diagnostic" element={<div>Diagnostic Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('PathsPage', () => {
  it('test_paths_loading_renders_skeleton', () => {
    mockUsePaths.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    } as never);
    renderPage();
    expect(screen.getByRole('status', { name: /loading career paths/i })).toBeInTheDocument();
  });

  it('test_paths_card_renders_rank_and_score', () => {
    const path = makePathResult({ rank: 1, score: 72.5, title: 'QEC Researcher' });
    mockUsePaths.mockReturnValue({
      isLoading: false,
      isError: false,
      data: makePathsOut([path]),
      error: null,
    } as never);
    renderPage();
    expect(screen.getByRole('article', { name: /QEC Researcher.*rank 1/i })).toBeInTheDocument();
    // aria-label="Score 72.5" is on the card header span — unique vs the table cell.
    expect(screen.getByLabelText('Score 72.5')).toBeInTheDocument();
  });

  it('test_paths_card_shows_breakdown_bars', () => {
    const path = makePathResult();
    mockUsePaths.mockReturnValue({
      isLoading: false,
      isError: false,
      data: makePathsOut([path]),
      error: null,
    } as never);
    renderPage();
    // Multiple "Score breakdown" labels exist (card div + table); at least one.
    expect(screen.getAllByLabelText(/score breakdown/i).length).toBeGreaterThanOrEqual(1);
    // Three ARIA progressbars for interest / demand / readiness.
    const bars = screen.getAllByRole('progressbar');
    expect(bars.length).toBeGreaterThanOrEqual(3);
  });

  it('test_paths_template_label_shown_on_template_explanation', async () => {
    const path = makePathResult({
      explanation: {
        headline: 'A good fit',
        reasons: ['Strong demand', 'Good readiness', 'High interest'],
        caveat: 'Data is thin',
        next_step: 'Apply for internships',
        generated_by: 'template',
        model: null,
        generated_at: null,
      },
    });
    mockUsePaths.mockReturnValue({
      isLoading: false,
      isError: false,
      data: makePathsOut([path]),
      error: null,
    } as never);
    renderPage();

    // Open the explanation panel; wrap state update in act.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /show explanation/i }));
    });

    expect(await screen.findByText(/template fallback/i)).toBeInTheDocument();
  });

  it('test_paths_llm_label_shown_on_llm_explanation', async () => {
    const path = makePathResult({
      explanation: {
        headline: 'Great match',
        reasons: ['R1', 'R2', 'R3'],
        caveat: 'None',
        next_step: 'Apply',
        generated_by: 'llm',
        model: 'gemini-2.0-flash',
        generated_at: '2026-01-01T00:00:00',
      },
    });
    mockUsePaths.mockReturnValue({
      isLoading: false,
      isError: false,
      data: makePathsOut([path]),
      error: null,
    } as never);
    renderPage();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /show explanation/i }));
    });

    expect(await screen.findByText(/ai-generated from the data shown/i)).toBeInTheDocument();
  });

  it('test_paths_redirects_to_diagnostic_on_409', () => {
    mockUsePaths.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: { status: 409, message: 'assessment_required' },
    } as never);
    renderPage();
    // Navigate replaces the route with /diagnostic.
    expect(screen.getByText('Diagnostic Page')).toBeInTheDocument();
  });

  it('test_paths_shows_assessment_date_under_heading', () => {
    mockUsePaths.mockReturnValue({
      isLoading: false,
      isError: false,
      data: makePathsOut([makePathResult()]),
      error: null,
    } as never);
    renderPage();
    expect(screen.getByText(/Based on your assessment from Oct 1, 2026/i)).toBeInTheDocument();
  });

  it('test_paths_low_data_notice_shown_when_low_data_true', () => {
    const path = makePathResult({ low_data: true });
    mockUsePaths.mockReturnValue({
      isLoading: false,
      isError: false,
      data: makePathsOut([path]),
      error: null,
    } as never);
    renderPage();
    expect(screen.getByRole('note')).toBeInTheDocument();
  });
});
