/**
 * ResultsPage tests: verifies rendering of the "See your paths" link and diagnostic results.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ResultsPage } from './ResultsPage';
import type { AssessmentResult } from '../types/api';

vi.mock('../features/diagnostic/components/ReadinessRadar', () => ({
  ReadinessRadar: () => <div data-testid="readiness-radar" />,
}));
vi.mock('../features/diagnostic/components/ScoreBars', () => ({
  ScoreBars: () => <div data-testid="score-bars" />,
}));
vi.mock('../features/diagnostic/components/FeedbackList', () => ({
  FeedbackList: () => <div data-testid="feedback-list" />,
}));

vi.mock('../features/diagnostic/hooks/useDiagnostic', () => ({
  useLatestAssessment: vi.fn(),
  useQuiz: vi.fn(() => ({
    data: { questions: [] },
  })),
}));

vi.mock('../features/pulse/hooks/usePulse', () => ({
  useTaxonomy: vi.fn(() => ({
    data: { subfields: [] },
  })),
}));

vi.mock('../lib/profileId', () => ({
  getOrCreateProfileId: vi.fn(() => 'test-profile'),
}));

vi.mock('../features/diagnostic/draft', () => ({
  loadDraft: vi.fn(() => ({ answers: {} })),
}));

import { useLatestAssessment } from '../features/diagnostic/hooks/useDiagnostic';
const mockUseLatestAssessment = vi.mocked(useLatestAssessment);

const SAMPLE_RESULT: AssessmentResult = {
  assessment_id: 1,
  profile_id: 'test-profile',
  taken_at: '2026-01-01T00:00:00Z',
  scores: { qec: 80 },
  interests: { qec: 90 },
  per_question: [],
  weak_concepts: [],
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/diagnostic/results']}>
        <ResultsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ResultsPage', () => {
  it('renders "See your paths" button linking to /paths', () => {
    mockUseLatestAssessment.mockReturnValue({
      data: SAMPLE_RESULT,
      isLoading: false,
      isError: false,
      error: null,
    } as never);

    renderPage();
    const link = screen.getByRole('link', { name: /see your paths/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/paths');
  });
});
