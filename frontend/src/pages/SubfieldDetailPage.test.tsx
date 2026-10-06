/**
 * SubfieldDetailPage tests: loading skeleton, error state, and detail rendering.
 * Uses a mock for useSubfieldDetail to avoid real network calls.
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { SubfieldDetail } from '../types/api';
import { SubfieldDetailPage } from './SubfieldDetailPage';

// Mock the hook so we never call the real API
vi.mock('../features/pulse/hooks/usePulse', () => ({
  useSubfieldDetail: vi.fn(),
}));

import { useSubfieldDetail } from '../features/pulse/hooks/usePulse';
const mockUseDetail = vi.mocked(useSubfieldDetail);

const DETAIL: SubfieldDetail = {
  subfield_id: 'qec',
  name: 'Quantum Error Correction',
  description: 'Protecting quantum information from noise.',
  active_postings: 5,
  extra_postings: 1,
  internship_postings: 1,
  new_this_week: null,
  tracking_since: '2026-10-01',
  top_companies: ['Riverlane'],
  low_data: true,
  top_skills: [{ skill_id: 'python', name: 'Python', share: 0.8 }],
  themes: [{ label: 'Surface codes', summary: 'Surface code theme.', papers: [] }],
  seniority_mix: { mid: 2, intern: 1, unknown: 2 },
  phd_share: 0.4,
  extraction_coverage: 0.8,
  postings: [
    {
      id: 1,
      title: 'QEC Engineer',
      company: 'Riverlane',
      location: 'London',
      via: 'LinkedIn',
      apply_url: 'https://example.com/apply',
      is_internship: false,
      first_seen_at: '2026-10-01T12:00:00',
      snippet: 'Looking for a QEC engineer...',
    },
  ],
};

function renderPage(subfieldId = 'qec') {
  return render(
    <MemoryRouter initialEntries={[`/pulse/${subfieldId}`]}>
      <Routes>
        <Route path="/pulse/:subfieldId" element={<SubfieldDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SubfieldDetailPage', () => {
  it('renders a loading skeleton when data is loading', () => {
    mockUseDetail.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as ReturnType<typeof useSubfieldDetail>);

    renderPage();

    expect(screen.getByLabelText('Loading subfield detail')).toBeInTheDocument();
  });

  it('renders an error state when the request fails', () => {
    mockUseDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
    } as ReturnType<typeof useSubfieldDetail>);

    renderPage();

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Failed to load subfield detail/i)).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('renders detail data: heading, counts, skills, mix, themes, postings', () => {
    mockUseDetail.mockReturnValue({
      data: DETAIL,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof useSubfieldDetail>);

    renderPage();

    expect(screen.getByRole('heading', { name: /Quantum Error Correction/i })).toBeInTheDocument();
    // Skill bar
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getAllByText('80%').length).toBeGreaterThan(0);
    // Mix chip
    expect(screen.getByText(/PhD required: 40%/)).toBeInTheDocument();
    // Research theme
    expect(screen.getByText('Surface codes')).toBeInTheDocument();
    // Posting
    expect(screen.getByText('QEC Engineer')).toBeInTheDocument();
    expect(screen.getByText(/Riverlane/)).toBeInTheDocument();
    // Coverage note
    expect(screen.getByText(/Coverage: 80% of postings extracted/)).toBeInTheDocument();
  });
});
