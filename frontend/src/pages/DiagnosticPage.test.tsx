/**
 * DiagnosticPage tests: stepper navigation, "Not sure" selection and
 * sessionStorage draft persistence (plan 3.6). The quiz and taxonomy hooks
 * are mocked so no network call happens.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DiagnosticPage } from './DiagnosticPage';
import type { QuizResponse } from '../types/api';

vi.mock('../features/diagnostic/hooks/useDiagnostic', () => ({
  useQuiz: vi.fn(),
  useSubmitAssessment: vi.fn(() => ({
    mutateAsync: vi.fn().mockResolvedValue({ assessment_id: 1 }),
    isPending: false,
  })),
  useLatestAssessment: vi.fn(),
}));
vi.mock('../features/pulse/hooks/usePulse', () => ({
  useTaxonomy: vi.fn(() => ({
    data: {
      subfields: [
        {
          id: 'qec',
          name: 'Quantum Error Correction',
          description: '',
          sort_order: 1,
          is_scored: true,
        },
        {
          id: 'hardware',
          name: 'Quantum Hardware',
          description: '',
          sort_order: 2,
          is_scored: true,
        },
      ],
    },
  })),
}));
vi.mock('../lib/profileId', () => ({
  ensureProfileId: vi.fn().mockResolvedValue('test-profile'),
}));

import { useQuiz } from '../features/diagnostic/hooks/useDiagnostic';
const mockUseQuiz = vi.mocked(useQuiz);

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

beforeEach(() => {
  sessionStorage.clear();
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

  it('selects "Not sure" and keeps it through next/back', () => {
    renderPage();
    startQuestions();

    fireEvent.click(screen.getByRole('button', { name: 'Not sure' }));
    fireEvent.click(screen.getByRole('button', { name: /next question|skip question/i }));
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
    fireEvent.click(screen.getByRole('button', { name: /next question|skip question/i }));
    expect(screen.getByText(/question 2 of 2/i)).toBeInTheDocument();

    unmount();
    renderPage(); // "refresh": a fresh mount reads the saved draft

    await waitFor(() => {
      expect(screen.getByText(/question 2 of 2/i)).toBeInTheDocument();
    });
  });

  it('warns on the review step when questions are unanswered', () => {
    renderPage();
    startQuestions();
    // Skip answering: next -> next lands on review with 2 unanswered.
    fireEvent.click(screen.getByRole('button', { name: /next question|skip question/i }));
    fireEvent.click(screen.getByRole('button', { name: /next question|skip question/i }));

    expect(screen.getByText(/2 question\(s\) unanswered/i)).toBeInTheDocument();
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
