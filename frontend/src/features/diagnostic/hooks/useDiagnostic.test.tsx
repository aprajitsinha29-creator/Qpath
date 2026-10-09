/**
 * Tests for useDiagnostic hooks reproducing submission with null profileId.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSubmitAssessment } from './useDiagnostic';

vi.mock('../api', () => ({
  submitAssessment: vi.fn().mockResolvedValue({
    assessment_id: 42,
    profile_id: 'mock-profile-id',
    taken_at: '2026-01-01T00:00:00Z',
    scores: {},
    interests: {},
    per_question: [],
    weak_concepts: [],
  }),
  getQuiz: vi.fn(),
  getLatestAssessment: vi.fn(),
}));

import { submitAssessment } from '../api';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('quantum_pathfinder_profile_id', 'stored-profile-uuid');
  vi.clearAllMocks();
});

describe('useSubmitAssessment', () => {
  it('submits assessment successfully when initialized with null or undefined profileId by falling back to stored profile', async () => {
    // DiagnosticPage passes null: useSubmitAssessment(null)
    const { result } = renderHook(() => useSubmitAssessment(null), {
      wrapper: createWrapper(),
    });

    const mutationResult = await result.current.mutateAsync({
      interests: { qec: 50 },
      answers: [],
    });

    expect(mutationResult.assessment_id).toBe(42);
    expect(submitAssessment).toHaveBeenCalledWith('stored-profile-uuid', expect.anything());
  });
});
