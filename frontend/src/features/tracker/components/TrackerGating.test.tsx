// Phase 5 frontend tests, part 2: TrendSparkline (hidden under 2 points,
// "tracking started" with 1, no-history state, text alternative) and the
// AppShell Opportunities nav gate (disabled until a path is tracked).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { TrendPoint } from '../../../types/api';
import { TrendSparkline } from './TrendSparkline';
import { AppShell } from '../../../components/layout/AppShell';

// ------------------------------------------------------------- TrendSparkline

describe('TrendSparkline', () => {
  const point = (date: string, active: number): TrendPoint => ({
    date,
    active,
    new: 0,
    internships: 0,
  });

  it('test_sparkline_hidden_with_fewer_than_two_points', () => {
    render(<TrendSparkline points={[point('2026-10-08', 4)]} subfieldName="QEC" />);
    expect(screen.queryByTestId('trend-sparkline')).not.toBeInTheDocument();
    expect(screen.getByTestId('trend-status')).toHaveTextContent(/tracking started 2026-10-08/);
  });

  it('test_sparkline_shows_no_history_yet_with_zero_points', () => {
    render(<TrendSparkline points={[]} subfieldName="QEC" />);
    expect(screen.queryByTestId('trend-sparkline')).not.toBeInTheDocument();
    expect(screen.getByTestId('trend-status')).toHaveTextContent(/no history yet/);
  });

  it('test_sparkline_renders_with_two_or_more_points', () => {
    render(
      <TrendSparkline
        points={[point('2026-10-08', 4), point('2026-10-09', 9)]}
        subfieldName="QEC"
      />,
    );
    expect(screen.getByTestId('trend-sparkline')).toBeInTheDocument();
  });

  it('test_sparkline_exposes_text_alternative', () => {
    render(
      <TrendSparkline
        points={[point('2026-10-08', 4), point('2026-10-09', 9)]}
        subfieldName="QEC"
      />,
    );
    const svg = screen.getByRole('img');
    expect(svg).toHaveAttribute(
      'aria-label',
      expect.stringMatching(/Active postings trend for QEC: 2026-10-08: 4, 2026-10-09: 9/),
    );
  });
});

// ------------------------------------------------------------- AppShell nav gate

// Mock the health badge so the shell test stays isolated from its query.
vi.mock('../../features/health/components/HealthBadge', () => ({
  HealthBadge: () => <div>health</div>,
}));

// Control what the chosen-path query returns per test.
const mockUseChosenPath = vi.fn();
vi.mock('../hooks/useTracker', () => ({
  useChosenPath: (...args: unknown[]) => mockUseChosenPath(...args),
}));

function renderShell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/']}>
        <AppShell />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AppShell Opportunities nav gate', () => {
  it('test_opportunities_nav_disabled_when_no_path_tracked', () => {
    mockUseChosenPath.mockReturnValue({ data: { profile_id: 'p1', chosen_path_id: null } });
    renderShell();
    expect(screen.queryByRole('link', { name: 'Opportunities' })).not.toBeInTheDocument();
    expect(screen.getByTestId('opportunities-nav-gate')).toBeInTheDocument();
  });

  it('test_opportunities_nav_enabled_once_a_path_is_tracked', async () => {
    mockUseChosenPath.mockReturnValue({
      data: { profile_id: 'p1', chosen_path_id: 'qec_engineer' },
    });
    renderShell();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Opportunities' })).toBeInTheDocument();
    });
    expect(screen.queryByTestId('opportunities-nav-gate')).not.toBeInTheDocument();
  });
});
