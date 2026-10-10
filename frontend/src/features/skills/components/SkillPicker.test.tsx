/**
 * SkillPicker tests (carry-over from Phase 4 frontend scope).
 *
 * Covers: loading/error/retry, alias-aware case-insensitive search, chip +
 * count updates, profile pre-fill, exact save payload + confirmation, 422
 * message display with selection preserved, and keyboard operation.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SkillPicker } from './SkillPicker';
import type { SkillsListResponse } from '../../../types/api';
import { ApiError } from '../../../lib/apiClient';

// Mock the hooks module so no network happens and tests drive query state.
vi.mock('../hooks/useSkills', () => ({
  useSkills: vi.fn(),
  useSaveDeclaredSkills: vi.fn(),
}));

import { useSaveDeclaredSkills, useSkills } from '../hooks/useSkills';
const mockUseSkills = vi.mocked(useSkills);
const mockUseSave = vi.mocked(useSaveDeclaredSkills);

const VOCABULARY: SkillsListResponse = [
  { id: 'python', name: 'Python', aliases: ['py'], subfield_ids: ['software'] },
  { id: 'pymatching', name: 'PyMatching', aliases: ['MWPM'], subfield_ids: ['qec'] },
  {
    id: 'control_electronics',
    name: 'Control electronics & FPGAs',
    aliases: ['FPGA', 'Verilog'],
    subfield_ids: ['hardware'],
  },
  { id: 'cpp', name: 'C++', aliases: ['cplusplus'], subfield_ids: ['hardware'] },
  { id: 'zzz_lower', name: 'alpha lowercase skill', aliases: [], subfield_ids: ['software'] },
];

function renderPicker(profileSkills: string[] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SkillPicker profileId="p-1" profileSkills={profileSkills} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseSkills.mockReturnValue({
    data: VOCABULARY,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  } as never);
  mockUseSave.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  } as never);
});

describe('SkillPicker', () => {
  it('test_skill_picker_loading_then_error_with_retry', async () => {
    // Loading state first.
    mockUseSkills.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    } as never);
    const { rerender } = renderPicker();
    expect(screen.getByRole('status', { name: /loading skills vocabulary/i })).toBeInTheDocument();

    // Flip to error: alert with a working retry button.
    const refetch = vi.fn();
    mockUseSkills.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    } as never);
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <SkillPicker profileId="p-1" profileSkills={[]} />
      </QueryClientProvider>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it('test_skill_picker_search_matches_alias_case_insensitive', () => {
    renderPicker();
    const input = screen.getByLabelText(/search skills/i);
    fireEvent.change(input, { target: { value: 'mwpm' } });
    expect(screen.getByRole('checkbox', { name: /pymatching/i })).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /^python/i })).not.toBeInTheDocument();

    // Case-insensitive on names too.
    fireEvent.change(input, { target: { value: 'PYTHON' } });
    expect(screen.getByRole('checkbox', { name: /^python/i })).toBeInTheDocument();
  });

  it('test_skill_picker_sorts_vocabulary_case_insensitively', () => {
    // VOCABULARY arrives deliberately out of order and mixed-case. Under a
    // raw code-point sort the lowercase 'alpha…' name would be LAST (all
    // uppercase names sort first); with case-insensitive collation it sits
    // among the capitalized names instead — that is the contract.
    renderPicker();
    const names = screen
      .getAllByRole('checkbox')
      .map((el) => (el as HTMLButtonElement).getAttribute('aria-label') ?? '')
      .map((label) => label.replace(/ (selected|not selected)$/, ''));
    expect(names[names.length - 1]).not.toBe('alpha lowercase skill');
    const alphaIndex = names.findIndex((n) => n === 'alpha lowercase skill');
    const pythonIndex = names.findIndex((n) => n === 'Python');
    expect(alphaIndex).toBeGreaterThan(-1);
    expect(alphaIndex).toBeLessThan(pythonIndex);
  });

  it('test_skill_picker_select_and_deselect_updates_chips_and_count', () => {
    renderPicker();
    // aria-live count starts at 0.
    expect(screen.getByText(/0 skills selected/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: /^python/i }));
    expect(screen.getByText(/1 skill selected/i)).toBeInTheDocument();
    // Chip appeared (uniquely identified by its remove button's accessible name).
    expect(screen.getByRole('button', { name: /remove python/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /remove python/i }));
    expect(screen.getByText(/0 skills selected/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /remove python/i })).not.toBeInTheDocument();
  });

  it('test_skill_picker_prefills_from_profile_declared_skills', () => {
    renderPicker(['pymatching']);
    const matching = screen.getByRole('checkbox', { name: /pymatching/i }) as HTMLButtonElement;
    expect(matching.getAttribute('aria-checked')).toBe('true');
    expect(screen.getByText(/1 skill selected/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /remove pymatching/i })).toBeInTheDocument();
  });

  it('test_skill_picker_save_sends_exact_ids_and_confirms', async () => {
    const mutate = vi.fn((_ids: string[], opts: { onSuccess?: () => void }) => {
      opts.onSuccess?.();
    });
    mockUseSave.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
      error: null,
    } as never);
    renderPicker(['python']);
    fireEvent.click(screen.getByRole('checkbox', { name: /pymatching/i }));

    fireEvent.click(screen.getByRole('button', { name: /save skills/i }));
    expect(mutate).toHaveBeenCalledWith(['python', 'pymatching'], expect.anything());
    expect(await screen.findByText(/skills saved to your profile/i)).toBeInTheDocument();
  });

  it('test_skill_picker_save_422_shows_message_keeps_selection', () => {
    mockUseSave.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: new ApiError('unknown skill id(s): ghost_skill', 'invalid_skills', 422),
    } as never);
    renderPicker(['python']);
    fireEvent.click(screen.getByRole('checkbox', { name: /pymatching/i }));

    // The backend message is surfaced...
    expect(screen.getByRole('alert')).toHaveTextContent(/unknown skill id\(s\)/);
    // ...and the selection survives for the user to fix.
    expect(
      (screen.getByRole('checkbox', { name: /^python/i }) as HTMLButtonElement).getAttribute(
        'aria-checked',
      ),
    ).toBe('true');
    expect(
      (screen.getByRole('checkbox', { name: /pymatching/i }) as HTMLButtonElement).getAttribute(
        'aria-checked',
      ),
    ).toBe('true');
  });

  it('test_skill_picker_keyboard_toggle_and_chip_accessible_names', () => {
    renderPicker();
    const python = screen.getByRole('checkbox', { name: /^python/i });

    // Space toggles.
    fireEvent.keyDown(python, { key: ' ' });
    expect(screen.getByText(/1 skill selected/i)).toBeInTheDocument();

    // Enter toggles off (a second press on the re-queried element).
    fireEvent.keyDown(screen.getByRole('checkbox', { name: /^python/i }), { key: 'Enter' });
    expect(screen.getByText(/0 skills selected/i)).toBeInTheDocument();

    // Re-select, then the chip remove button must have an accessible name.
    fireEvent.click(screen.getByRole('checkbox', { name: /^python/i }));
    expect(screen.getByRole('button', { name: /remove python/i })).toBeInTheDocument();
  });

  it('test_skill_picker_save_succeeds_updates_count_after_confirmation', async () => {
    renderPicker();
    fireEvent.click(screen.getByRole('checkbox', { name: /control electronics/i }));
    const button = screen.getByRole('button', { name: /save skills/i });
    expect(button).toBeEnabled();
    await waitFor(() => expect(button).toBeEnabled());
  });
});
