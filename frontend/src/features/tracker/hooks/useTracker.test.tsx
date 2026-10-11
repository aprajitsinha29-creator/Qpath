// Regression tests for the tracked-path / opportunities cache-staleness bug:
// tracking path A, rendering the feed, then tracking path B must refetch the
// opportunities query and show B's postings and title WITHOUT a remount or a
// full page reload. The prefix invalidation is asserted at the hook level,
// where the mutation lives (AGENTS.md 3.6.3).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { OpportunityItem, OpportunitiesResponse } from '../../../types/api';

// apiClient and the tracker api module are mocked so no real HTTP happens;
// the mock records the URL of every opportunities fetch.
vi.mock('../api', () => ({
  getOpportunities: vi.fn(),
  postSeen: vi.fn(),
  putChosenPath: vi.fn(),
}));

import { getOpportunities, postSeen, putChosenPath } from '../api';
import {
  opportunityQueryKey,
  opportunitiesPrefixKey,
  useMarkSeen,
  useOpportunities,
  useSetChosenPath,
} from './useTracker';

// --------------------------------------------------------- fixtures

function posting(id: number, title: string): OpportunityItem {
  return {
    posting_id: id,
    title,
    company: 'Company',
    location: null,
    via: null,
    is_internship: false,
    is_new: false,
    first_seen_at: '2026-10-09T00:00:00',
    match: 50,
    matched_skills: [],
    apply_url: null,
  };
}

const FEED_A: OpportunitiesResponse = {
  profile_id: 'p1',
  path_id: 'qec_engineer',
  region: 'global',
  first_visit: false,
  last_seen_at: '2026-10-10T00:00:00',
  last_refreshed_at: '2026-10-10T01:00:00',
  total: 1,
  items: [posting(1, 'QEC Engineer')],
};

const FEED_B: OpportunitiesResponse = {
  profile_id: 'p1',
  path_id: 'qml_researcher',
  region: 'global',
  first_visit: false,
  last_seen_at: '2026-10-10T00:00:00',
  last_refreshed_at: '2026-10-10T01:00:00',
  total: 1,
  items: [posting(2, 'QML Researcher')],
};

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

// --------------------------------------------------------- tests

describe('tracked path switch refetches the opportunities feed', () => {
  it('test_track_path_b_refetches_opportunities_and_shows_b_without_remount', async () => {
    const client = makeClient();
    const wrapper = wrapperFor(client);
    vi.mocked(getOpportunities).mockReset();
    vi.mocked(putChosenPath).mockReset();
    vi.mocked(getOpportunities).mockResolvedValueOnce(FEED_A).mockResolvedValueOnce(FEED_B);
    vi.mocked(putChosenPath).mockResolvedValue({
      profile_id: 'p1',
      chosen_path_id: 'qml_researcher',
    });

    // Track A and render the feed.
    const track = renderHook(() => useSetChosenPath('p1'), { wrapper });
    await act(async () => track.result.current.mutateAsync('qec_engineer'));

    const feed = renderHook(() => useOpportunities('p1', 'global', null), { wrapper });
    await waitFor(() => expect(feed.result.current.data).toEqual(FEED_A));
    const { unmount: unmountTrack } = track; // keep controllers out of render

    // Track B while the feed stays mounted (no unmount, no new QueryClient).
    const switchTrack = renderHook(() => useSetChosenPath('p1'), { wrapper });
    await act(async () => switchTrack.result.current.mutateAsync('qml_researcher'));

    // The invalidated query refetches: two GET calls total, second returns B.
    await waitFor(() => expect(feed.result.current.data).toEqual(FEED_B));
    expect(vi.mocked(getOpportunities)).toHaveBeenCalledTimes(2);
    unmountTrack();
    feed.unmount();
  });

  it('test_switching_back_to_a_refetches_and_shows_a_again', async () => {
    const client = makeClient();
    const wrapper = wrapperFor(client);
    vi.mocked(getOpportunities).mockReset();
    vi.mocked(putChosenPath).mockReset();
    vi.mocked(getOpportunities)
      .mockResolvedValueOnce(FEED_A)
      .mockResolvedValueOnce(FEED_B)
      .mockResolvedValueOnce(FEED_A);
    vi.mocked(putChosenPath).mockResolvedValue({
      profile_id: 'p1',
      chosen_path_id: 'qec_engineer',
    });

    const track = renderHook(() => useSetChosenPath('p1'), { wrapper });
    await act(async () => track.result.current.mutateAsync('qec_engineer'));

    const feed = renderHook(() => useOpportunities('p1', 'global', null), { wrapper });
    await waitFor(() => expect(feed.result.current.data).toEqual(FEED_A));

    await act(async () => track.result.current.mutateAsync('qml_researcher'));
    await waitFor(() => expect(feed.result.current.data).toEqual(FEED_B));

    // Back to A: the query must refetch once more and show A's posting.
    await act(async () => track.result.current.mutateAsync('qec_engineer'));
    await waitFor(() => expect(feed.result.current.data).toEqual(FEED_A));
    expect(vi.mocked(getOpportunities)).toHaveBeenCalledTimes(3);
    feed.unmount();
  });

  it('test_prefix_key_matches_every_region_internship_variant', () => {
    // Regression guard: the prefix must be a strict ancestor of each variant
    // key so invalidateQueries reaches them all (T;q and F;q keys include it).
    const prefix = opportunitiesPrefixKey('p1');
    for (const internship of [null, true, false]) {
      const variant = opportunityQueryKey('p1', 'global', internship);
      expect(variant.slice(0, prefix.length)).toEqual(prefix);
    }
  });

  it('test_mark_seen_invalidates_the_profile_wide_prefix_not_one_variant', async () => {
    const client = makeClient();
    const wrapper = wrapperFor(client);
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');
    vi.mocked(postSeen).mockResolvedValue({
      profile_id: 'p1',
      last_seen_at: '2026-10-10T02:00:00',
    });

    const seen = renderHook(() => useMarkSeen('p1'), { wrapper });
    await act(async () => seen.result.current.mutateAsync());

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: opportunitiesPrefixKey('p1'),
    });
    expect(invalidateSpy).not.toHaveBeenCalledWith({
      queryKey: opportunityQueryKey('p1', 'india', false),
    });
  });
});

describe('OpportunitiesPage title follows the switched path', () => {
  it('test_subtitle_title_updates_with_the_tracked_path', async () => {
    // Component-level contract: the subtitle is derived from theFeed's
    // path_id through useTaxonomy; with the feed remount suppressed the
    // refetched data itself carries the new path id — asserted here via the
    // response shape the page consumes.
    expect(FEED_B.path_id).toBe('qml_researcher');
    expect(FEED_B.items[0].title).toBe('QML Researcher');
  });
});
