// Phase 5 frontend tests, part 1: TrackPathButton (PUT chosen-path + switch
// label), OpportunityCard (match badge / NEW badge gating), and
// LastRefreshedPill (relative time vs the "never refreshed" state).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { OpportunityItem } from '../../../types/api';
import { OpportunityCard } from './OpportunityCard';
import { LastRefreshedPill } from './LastRefreshedPill';
import { TrackPathButton } from './TrackPathButton';

// Mock the tracker API module so no fetch happens (AGENTS 3.7.1).
vi.mock('../api', () => ({
  putChosenPath: vi.fn(),
  postSeen: vi.fn(),
  getOpportunities: vi.fn(),
}));

import { putChosenPath } from '../api';
const mockPutChosenPath = vi.mocked(putChosenPath);

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockPutChosenPath.mockResolvedValue({ profile_id: 'p1', chosen_path_id: 'qec_engineer' });
});

// ------------------------------------------------------------- TrackPathButton

describe('TrackPathButton', () => {
  it('test_trackpathbutton_puts_chosen_path_and_switches_to_tracking', async () => {
    renderWithClient(<TrackPathButton profileId="p1" pathId="qec_engineer" trackedPathId={null} />);

    const button = screen.getByRole('button', { name: /track qec_engineer/i });
    button.click();
    await waitFor(() => {
      expect(mockPutChosenPath).toHaveBeenCalledWith('p1', 'qec_engineer');
    });
  });

  it('test_trackpathbutton_shows_tracking_when_path_is_the_tracked_one', () => {
    renderWithClient(
      <TrackPathButton profileId="p1" pathId="qec_engineer" trackedPathId="qec_engineer" />,
    );
    expect(screen.getByRole('button', { name: /tracking qec_engineer/i })).toBeInTheDocument();
  });

  it('test_trackpathbutton_offers_switch_when_another_path_is_tracked', () => {
    renderWithClient(
      <TrackPathButton profileId="p1" pathId="hardware_engineer" trackedPathId="qec_engineer" />,
    );
    expect(screen.getByRole('button', { name: /track hardware_engineer/i }).textContent).toMatch(
      /Switch to this path/i,
    );
  });
});

// ------------------------------------------------------------- OpportunityCard

function makeItem(overrides: Partial<OpportunityItem> = {}): OpportunityItem {
  return {
    posting_id: 1,
    title: 'QEC Research Intern',
    company: 'Riverlane',
    location: 'Cambridge',
    via: 'LinkedIn',
    apply_url: 'https://example.com/apply',
    is_internship: true,
    first_seen_at: '2026-10-09T00:00:00',
    is_new: true,
    match: 82,
    matched_skills: ['python', 'stim'],
    ...overrides,
  };
}

describe('OpportunityCard', () => {
  it('test_match_badge_shows_number', () => {
    render(<OpportunityCard item={makeItem({ match: 82 })} firstVisit={false} hasDeclaredSkills />);
    expect(screen.getByTestId('match-badge')).toHaveTextContent('82%');
  });

  it('test_match_badge_shows_not_enough_info_when_skills_declared', () => {
    // Declared skills exist but this posting has nothing extracted: null →
    // honest "Not enough info", never a percentage.
    render(
      <OpportunityCard item={makeItem({ match: null })} firstVisit={false} hasDeclaredSkills />,
    );
    expect(screen.getByTestId('match-badge')).toHaveTextContent('Not enough info');
  });

  it('test_match_null_without_declared_skills_shows_add_skills_link', () => {
    // No declared skills → invite to the panel instead of a percentage.
    render(
      <OpportunityCard
        item={makeItem({ match: null })}
        firstVisit={false}
        hasDeclaredSkills={false}
      />,
    );
    const badge = screen.getByTestId('match-badge');
    expect(badge.tagName).toBe('A');
    expect(badge).toHaveTextContent('Add your skills to see a match');
    expect(badge).toHaveAttribute('href', '#skills-panel');
  });

  it('test_match_null_percentage_never_rendered', () => {
    render(
      <OpportunityCard
        item={makeItem({ match: null })}
        firstVisit={false}
        hasDeclaredSkills={false}
      />,
    );
    expect(screen.getByTestId('match-badge').textContent).not.toMatch(/%\s*match/);
  });

  it('test_new_badge_shown_when_is_new_and_not_first_visit', () => {
    render(
      <OpportunityCard item={makeItem({ is_new: true })} firstVisit={false} hasDeclaredSkills />,
    );
    expect(screen.getByTestId('new-badge')).toBeInTheDocument();
  });

  it('test_skills_link_scrolls_and_focuses_panel', () => {
    // The anchor's default jump is prevented; the panel gets focus instead.
    const panel = document.createElement('div');
    panel.id = 'skills-panel';
    const panelButton = document.createElement('button');
    panel.appendChild(panelButton);
    document.body.appendChild(panel);
    // jsdom has no scrollIntoView; stub it so the handler runs.
    panel.scrollIntoView = vi.fn();
    const focusSpy = vi.spyOn(panelButton, 'focus');

    render(
      <OpportunityCard
        item={makeItem({ match: null })}
        firstVisit={false}
        hasDeclaredSkills={false}
      />,
    );
    const badge = screen.getByTestId('match-badge');
    fireEvent.click(badge);

    expect(focusSpy).toHaveBeenCalledTimes(1);
    panel.remove();
  });

  it('test_new_badge_hidden_on_first_visit', () => {
    render(<OpportunityCard item={makeItem({ is_new: true })} firstVisit hasDeclaredSkills />);
    expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument();
  });

  it('test_apply_link_uses_noopener_noreferrer', () => {
    render(<OpportunityCard item={makeItem()} firstVisit={false} hasDeclaredSkills />);
    const link = screen.getByRole('link', { name: 'Apply' });
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveAttribute('target', '_blank');
  });
});

// ------------------------------------------------------------- LastRefreshedPill

describe('LastRefreshedPill', () => {
  // Use a timestamp 3 hours before "now" so the relative formatter is stable.
  const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();

  it('test_last_refreshed_pill_shows_relative_time', () => {
    render(<LastRefreshedPill iso={threeHoursAgo} />);
    expect(screen.getByTestId('last-refreshed-pill')).toHaveTextContent(/refreshed 3h ago/i);
  });

  it('test_last_refreshed_pill_shows_never_state_for_null', () => {
    render(<LastRefreshedPill iso={null} />);
    expect(screen.getByTestId('last-refreshed-pill')).toHaveTextContent(/never refreshed/i);
  });
});
