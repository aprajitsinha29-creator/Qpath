// Regression test for the Phase 5 acceptance behavior: saving declared
// skills from the opportunities SkillPicker panel must refetch the
// opportunities feed (match scores = 0.6 × skill overlap depend on the
// declared set — plan 5.5).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SkillPicker } from '../components/SkillPicker';

// Mock the API module so no fetch happens; the real hooks run.
vi.mock('../api', () => ({
  getSkills: vi.fn(),
  putDeclaredSkills: vi.fn(),
}));

import { putDeclaredSkills } from '../api';
const mockPut = vi.mocked(putDeclaredSkills);

beforeEach(() => {
  vi.clearAllMocks();
  mockPut.mockResolvedValue({
    profile_id: 'p1',
    created_at: '2026-10-01T00:00:00',
    interests: {},
    declared_skills: ['python'],
    chosen_path_id: null,
  });
});

describe('useSaveDeclaredSkills invalidates the opportunities feed', () => {
  it('test_saving_declared_skills_refetches_opportunities', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    // Prime the vocabulary cache so the picker renders immediately.
    client.setQueryData(
      ['skills'],
      [{ id: 'python', name: 'Python', aliases: ['py'], subfield_ids: ['software'] }],
    );
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    render(
      <QueryClientProvider client={client}>
        <SkillPicker profileId="p1" profileSkills={[]} />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('checkbox', { name: /^python/i }));
    fireEvent.click(screen.getByRole('button', { name: /save skills/i }));

    await vi.waitFor(() => {
      // The scoped prefix must reach every region/internship variant of this
      // profile's feed (and not other profiles' caches).
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ['opportunities', 'p1'],
      });
    });
  });
});
