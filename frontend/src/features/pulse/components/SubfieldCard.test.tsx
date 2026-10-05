/**
 * SubfieldCard tests: renders counts, the "tracking since" fallback instead of
 * null new_this_week, the growth number once available, and the low-data badge.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { PulseCard } from '../../../types/api';
import { SubfieldCard } from './SubfieldCard';

function makeCard(overrides: Partial<PulseCard> = {}): PulseCard {
  return {
    subfield_id: 'qec',
    name: 'Quantum Error Correction',
    description: 'Protecting quantum information from noise.',
    active_postings: 3,
    extra_postings: 1,
    internship_postings: 1,
    new_this_week: null,
    tracking_since: '2026-10-04',
    top_companies: ['Riverlane', 'Alice & Bob'],
    low_data: true,
    ...overrides,
  };
}

describe('SubfieldCard', () => {
  it('renders counts, top companies and the low-data badge', () => {
    render(<SubfieldCard card={makeCard()} region="global" internshipOnly={false} />);

    expect(screen.getByLabelText('Quantum Error Correction market pulse')).toBeInTheDocument();
    expect(screen.getByTestId('active-postings')).toHaveTextContent('3');
    expect(screen.getByTestId('internship-postings')).toHaveTextContent('1');
    expect(screen.getByText('low data')).toBeInTheDocument();
    expect(screen.getByText('Riverlane, Alice & Bob')).toBeInTheDocument();
  });

  it('shows "tracking since" when new_this_week is null (single-day corpus)', () => {
    render(
      <SubfieldCard
        card={makeCard({ new_this_week: null, tracking_since: '2026-10-04' })}
        region="global"
        internshipOnly={false}
      />,
    );

    expect(screen.getByTestId('new-this-week')).toHaveTextContent(/Tracking since 2026-10-04/);
    expect(screen.queryByText(/new this week/)).not.toBeInTheDocument();
  });

  it('shows the new-this-week number once the corpus spans 2+ days', () => {
    render(
      <SubfieldCard
        card={makeCard({ new_this_week: 5, tracking_since: '2026-10-01' })}
        region="global"
        internshipOnly={false}
      />,
    );

    expect(screen.getByTestId('new-this-week')).toHaveTextContent(/\+5 new this week/);
  });

  it('shows a no-data hint when nothing was captured yet', () => {
    render(
      <SubfieldCard
        card={makeCard({
          active_postings: 0,
          extra_postings: 0,
          internship_postings: 0,
          new_this_week: null,
          tracking_since: null,
          top_companies: [],
        })}
        region="india"
        internshipOnly={false}
      />,
    );

    expect(screen.getByTestId('new-this-week')).toHaveTextContent(/No postings captured yet/);
  });

  it('renders without the low-data badge when evidence is sufficient', () => {
    render(
      <SubfieldCard
        card={makeCard({ low_data: false, active_postings: 12 })}
        region="global"
        internshipOnly={false}
      />,
    );

    expect(screen.queryByText('low data')).not.toBeInTheDocument();
  });
});
