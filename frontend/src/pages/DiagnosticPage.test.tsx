/**
 * DiagnosticPage tests: stepper navigation, "Not sure" selection and
 * sessionStorage draft persistence (plan 3.6). The quiz and taxonomy hooks
 * are mocked so no network call happens.
 *
 * Regression coverage (bug fix): untouched interest sliders submit the
 * displayed defaults, incomplete drafts load repaired, review counts and
 * navigation links behave as advertised.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DiagnosticPage } from './DiagnosticPage';
import type { QuizResponse, SubfieldOut } from '../types/api';

const mutateAsync = vi.fn().mockResolvedValue({ assessment_id: 1 });

vi.mock('../features/diagnostic/hooks/useDiagnostic', () => ({
  useQuiz: vi.fn(),
  useSubmitAssessment: vi.fn(() => ({
    mutateAsync,
    isPending: false,
  })),
  useLatestAssessment: vi.fn(),
}));
vi.mock('../features/pulse/hooks/usePulse', () => ({
  useTaxonomy: vi.fn(() => ({
    data: {
      subfields: SCORED_SUBFIELDS,
    },
  })),
}));
vi.mock('../lib/profileId', () => ({
  ensureProfileId: vi.fn().mockResolvedValue('test-profile'),
}));

import { useQuiz } from '../features/diagnostic/hooks/useDiagnostic';
const mockUseQuiz = vi.mocked(useQuiz);

/** The six scored subfields the backend requires in every submission. */
const SCORED_SUBFIELDS: SubfieldOut[] = [
  { id: 'qec', name: 'QEC', description: '', sort_order: 1, is_scored: true },
  { id: 'hardware', name: 'Hardware', description: '', sort_order: 2, is_scored: true },
  { id: 'software', name: 'Software', description: '', sort_order: 3, is_scored: true },
  { id: 'algorithms', name: 'Algorithms', description: '', sort_order: 4, is_scored: true },
  { id: 'qml', name: 'QML', description: '', sort_order: 5, is_scored: true },
  { id: 'crypto_net', name: 'Crypto', description: '', sort_order: 6, is_scored: true },
];

const QUIZ: QuizResponse = {
  questions: [
    {
      id: 'qec-1',
      subfield_id: 'qec',
      concept_id: 'qec.stabilizer_codes',
      difficulty: 1,
      stem: 'What do syndrome measurements do?',
      options: ['A', 'B', 'C', 'D'],
    },
    {
      id: 'qec-2',
      subfield_id: 'qec',
      concept_id: 'qec.surface_code',
      difficulty: 2,
      stem: 'Second question?',
      options: ['W', 'X', 'Y', 'Z'],
    },
  ],
};

/** 18-question quiz so the review wording can be checked at full length. */
const QUIZ_18: QuizResponse = {
  questions: Array.from({ length: 18 }, (_, i) => ({
    id: `q${i + 1}`,
    subfield_id: 'qec',
    concept_id: `qec.c${i}`,
    difficulty: 1,
    stem: `Question ${i + 1}?`,
    options: ['A', 'B', 'C', 'D'],
  })),
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/diagnostic']}>
        <DiagnosticPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function startQuestions() {
  fireEvent.click(screen.getByRole('button', { name: /start questions/i }));
}

function goToReview() {
  startQuestions();
  fireEvent.click(screen.getByRole('button', { name: /skip question|next question/i }));
  fireEvent.click(screen.getByRole('button', { name: /skip question|next question/i }));
  fireEvent.click(screen.getByRole('button', { name: /review submission/i }));
}

beforeEach(() => {
  sessionStorage.clear();
  mutateAsync.mockClear();
  mockUseQuiz.mockReturnValue({
    data: QUIZ,
    isLoading: false,
    isError: false,
    error: null,
  } as never);
});

describe('DiagnosticPage', () => {
  it('renders interest sliders first, then moves to questions', () => {
    renderPage();

    expect(screen.getByRole('group', { name: /how interested/i })).toBeInTheDocument();
    startQuestions();
    expect(screen.getByText(/question 1 of 2/i)).toBeInTheDocument();
    expect(screen.getByText('What do syndrome measurements do?')).toBeInTheDocument();
  });

  it('submits the displayed interest defaults when sliders are untouched', async () => {
    renderPage();
    goToReview();

    fireEvent.click(screen.getByRole('button', { name: /yes, submit/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1);
    });
    const payload = mutateAsync.mock.calls[0][0];
    expect(payload.interests).toEqual({
      qec: 1,
      hardware: 1,
      software: 1,
      algorithms: 1,
      qml: 1,
      crypto_net: 1,
    });
  });

  it('loads stored drafts with empty interests as the displayed defaults', () => {
    sessionStorage.setItem(
      'quantum_pathfinder_diagnostic_draft',
      JSON.stringify({ step: 0, interests: {}, answers: {} }),
    );
    renderPage();

    // Six sliders shown at 1/5, exactly what will be submitted.
    const sliders = screen.getAllByRole('slider');
    expect(sliders).toHaveLength(6);
    for (const slider of sliders) {
      expect(slider).toHaveValue('1');
    }
  });

  it('only counts questions with no selection at all as unanswered', () => {
    mockUseQuiz.mockReturnValue({
      data: QUIZ_18,
      isLoading: false,
      isError: false,
      error: null,
    } as never);
    renderPage();
    startQuestions();

    // Answer all 18 with "Not sure" — a deliberate selection, not a gap.
    for (let i = 0; i < 18; i += 1) {
      fireEvent.click(screen.getByRole('button', { name: 'Not sure' }));
      fireEvent.click(screen.getByRole('button', { name: 'Next question' }));
    }

    expect(screen.getByText('Ready to submit?')).toBeInTheDocument();
    expect(screen.queryByText(/question\(s\)/i)).not.toBeInTheDocument();
  });

  it('navigates back from question 1 to the interest step', () => {
    renderPage();
    startQuestions();
    expect(screen.getByText(/question 1 of 2/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));

    expect(screen.getByRole('group', { name: /how interested/i })).toBeInTheDocument();
  });

  it('offers edit/back/start-over on the review screen and start over clears the draft', async () => {
    renderPage();
    goToReview();

    expect(screen.getByRole('button', { name: 'Edit interests' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Back to questions' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start over' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Start over' }));

    await waitFor(() => {
      expect(sessionStorage.getItem('quantum_pathfinder_diagnostic_draft')).toBeNull();
    });
    expect(screen.getByRole('group', { name: /how interested/i })).toBeInTheDocument();
  });

  it('selects "Not sure" and keeps it through next/back', () => {
    renderPage();
    startQuestions();

    fireEvent.click(screen.getByRole('button', { name: 'Not sure' }));
    fireEvent.click(screen.getByRole('button', { name: 'Next question' }));
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));

    // "Not sure" stays selected (the draft persisted the null answer).
    expect(screen.getByRole('button', { name: 'Not sure' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('persists progress in sessionStorage across a simulated refresh', async () => {
    const { unmount } = renderPage();
    startQuestions();
    fireEvent.click(screen.getAllByRole('radio')[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Next question' }));
    expect(screen.getByText(/question 2 of 2/i)).toBeInTheDocument();

    unmount();
    renderPage(); // "refresh": a fresh mount reads the saved draft

    await waitFor(() => {
      expect(screen.getByText(/question 2 of 2/i)).toBeInTheDocument();
    });
  });

  it('warns on the review step with the accurate unanswered wording', () => {
    renderPage();
    startQuestions();
    // Skip answering: next -> next lands on review with 2 unselected.
    fireEvent.click(screen.getByRole('button', { name: /skip question|next question/i }));
    fireEvent.click(screen.getByRole('button', { name: /skip question|next question/i }));

    expect(screen.getByText(/2 question\(s\) with no answer selected/i)).toBeInTheDocument();
  });

  it('renders redirect notification banner when navigated from paths without assessment', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter
          initialEntries={[
            {
              pathname: '/diagnostic',
              state: { message: 'You need to take the orientation diagnostic first' },
            },
          ]}
        >
          <DiagnosticPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/diagnostic required first/i)).toBeInTheDocument();
    expect(
      screen.getByText('You need to take the orientation diagnostic first'),
    ).toBeInTheDocument();
  });
});
