// Phase 5 frontend tests, part 3: OpportunitiesPage flows — "Mark all as seen"
// posts /seen and refetches (badges clear), filters change request parameters,
// and loading/empty/error states exist (plan 5.6 frontend item 10).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { OpportunitiesResponse } from '../types/api';

// Mock the whole tracker data path; the page must go through these wrappers
// (AGENTS 3.6.2 — components never call fetch directly).
const mockGetOpportunities = vi.fn();
const mockPostSeen = vi.fn();
vi.mock('../features/tracker/api', () => ({
  getOpportunities: (...args: unknown[]) => mockGetOpportunities(...args),
  postSeen: (...args: unknown[]) => mockPostSeen(...args),
}));

vi.mock('../features/tracker/hooks/useTracker', async () => {
  const actual = await vi.importActual<typeof import('../features/tracker/hooks/useTracker')>(
    '../features/tracker/hooks/useTracker',
  );
  return actual;
});

vi.mock('../lib/profileId', () => ({
  getOrCreateProfileId: vi.fn(() => 'p1'),
}));

// SkillPicker loads the vocabulary; stub it — its behaviour is covered by its
// own test file and not needed for the page-level flows here.
vi.mock('../features/skills/components/SkillPicker', () => ({
  SkillPicker: () => <div>skillpicker</div>,
}));

vi.mock('../features/skills/hooks/useSkills', async () => {
  const actual = await vi.importActual<typeof import('../features/skills/hooks/useSkills')>(
    '../features/skills/hooks/useSkills',
  );
  return actual;
});

// Taxonomy (path title for the subtitle) — same cache the pulse feature uses.
vi.mock('../features/pulse/hooks/usePulse', () => ({
  useTaxonomy: vi.fn(() => ({
    data: {
      subfields: [],
      concepts: [],
      career_paths: [
        {
          id: 'qec_engineer',
          title: 'QEC Researcher / Engineer',
          subfield_id: 'qec',
          description: '',
          typical_titles: [],
        },
      ],
    },
  })),
}));

import { OpportunitiesPage } from './OpportunitiesPage';

/** Build a feed response; items default to one new match with a score. */
function makeFeed(overrides: Partial<OpportunitiesResponse> = {}): OpportunitiesResponse {
  return {
    profile_id: 'p1',
    path_id: 'qec_engineer',
    region: 'global',
    first_visit: false,
    total: 1,
    last_seen_at: '2026-10-09T12:00:00',
    last_refreshed_at: '2026-10-09T06:00:00',
    items: [
      {
        posting_id: 1,
        title: 'QEC Engineer',
        company: 'Riverlane',
        location: 'Cambridge',
        via: 'LinkedIn',
        apply_url: 'https://example.com/a',
        is_internship: false,
        first_seen_at: '2026-10-09T10:00:00',
        is_new: true,
        match: 77,
        matched_skills: ['python'],
      },
    ],
    ...overrides,
  };
}

function renderPage(client?: QueryClient) {
  const qc = client ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/opportunities']}>
        <OpportunitiesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockGetOpportunities.mockResolvedValue(makeFeed());
  mockPostSeen.mockResolvedValue({ profile_id: 'p1', last_seen_at: '2026-10-09T13:00:00' });
});

describe('OpportunitiesPage', () => {
  it('test_mark_all_as_seen_posts_seen_and_clears_badges', async () => {
    // First fetch (before seen) has new items; every later fetch (after the
    // seen marker) returns nothing new — as the backend would.
    const seenFeed = makeFeed({ items: [{ ...makeFeed().items[0], is_new: false }] });
    mockGetOpportunities.mockResolvedValueOnce(makeFeed());
    mockGetOpportunities.mockResolvedValue(seenFeed);

    renderPage();
    await screen.findByTestId('new-badge');

    fireEvent.click(screen.getByTestId('mark-seen-button'));

    await waitFor(
      () => {
        expect(mockPostSeen).toHaveBeenCalledWith('p1');
      },
      { timeout: 3000 },
    );

    await waitFor(
      () => {
        expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it('test_filters_change_request_parameters', async () => {
    renderPage();

    // Wait for the feed to load before interacting with the filters.
    await screen.findByText(/Mark all as seen/i);
    expect(mockGetOpportunities).toHaveBeenCalledWith('p1', {
      region: 'global',
      internship: null,
      limit: 50,
      offset: 0,
    });

    fireEvent.change(screen.getByLabelText('Region'), {
      target: { value: 'india' },
    });

    // The region change switches the query key → brief loading state; wait
    // for the filters to come back before touching the second one.
    await screen.findByLabelText('Internships');
    fireEvent.change(screen.getByLabelText('Internships'), {
      target: { value: 'only' },
    });

    await waitFor(
      () => {
        expect(mockGetOpportunities).toHaveBeenLastCalledWith('p1', {
          region: 'india',
          internship: true,
          limit: 50,
          offset: 0,
        });
      },
      { timeout: 3000 },
    );
  });

  it('test_loading_state_renders_skeleton', async () => {
    mockGetOpportunities.mockReturnValue(new Promise(() => undefined)); // never settles
    renderPage();
    expect(screen.getByRole('status', { name: /loading opportunities/i })).toBeInTheDocument();
  });

  it('test_empty_state_shown_when_feed_has_no_items', async () => {
    mockGetOpportunities.mockResolvedValue(makeFeed({ items: [], total: 0 }));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/No matched postings yet/i)).toBeInTheDocument();
    });
  });

  it('test_error_state_renders_with_retry', async () => {
    mockGetOpportunities.mockRejectedValue(new Error('boom'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('test_first_visit_shows_intro_note_instead_of_badges', async () => {
    mockGetOpportunities.mockResolvedValue(makeFeed({ first_visit: true }));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/First visit/i)).toBeInTheDocument();
    });
    expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument();
  });

  it('test_subtitle_shows_path_title_not_id', async () => {
    renderPage();
    await screen.findByText(/Mark all as seen/i);
    expect(
      screen.getByText(/Matched to your tracked path: QEC Researcher \/ Engineer/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/qec_engineer/)).not.toBeInTheDocument();
  });

  it('test_no_declared_skills_sorts_feed_by_first_seen_desc', async () => {
    // Two postings; the FIRST in the response is the OLDER one. With no
    // declared skills every match is null, so display falls back to
    // first_seen desc and the newer posting must come first.
    mockGetOpportunities.mockResolvedValue(
      makeFeed({
        items: [
          {
            posting_id: 1,
            title: 'Older posting',
            company: 'A',
            location: null,
            via: null,
            apply_url: null,
            is_internship: false,
            first_seen_at: '2026-10-01T00:00:00',
            is_new: false,
            match: null,
            matched_skills: [],
          },
          {
            posting_id: 2,
            title: 'Newer posting',
            company: 'B',
            location: null,
            via: null,
            apply_url: null,
            is_internship: false,
            first_seen_at: '2026-10-09T00:00:00',
            is_new: true,
            match: null,
            matched_skills: [],
          },
        ],
      }),
    );
    renderPage();

    // No skills declared (empty mock profile) → newer first.
    await screen.findByText('Newer posting');
    const list = screen.getByLabelText('Opportunities list');
    const firstArticle = list.querySelector('article')?.textContent ?? '';
    expect(firstArticle).toContain('Newer posting');
  });

  it('test_last_refreshed_pill_renders_from_feed', async () => {
    mockGetOpportunities.mockResolvedValue(makeFeed({ last_refreshed_at: null }));
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('last-refreshed-pill')).toHaveTextContent(/never refreshed/i);
    });
  });
});
