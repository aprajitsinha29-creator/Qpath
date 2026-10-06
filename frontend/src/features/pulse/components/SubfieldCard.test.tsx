/**
 * SubfieldCard tests: renders counts, the "tracking since" fallback instead of
 * null new_this_week, the growth number once available, and the low-data badge.
 * Phase 2: top_skills and themes fields exist on the card type.
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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
    // Phase 2 additive fields (empty by default — matches the schema)
    top_skills: [],
    themes: [],
    ...overrides,
  };
}

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('SubfieldCard', () => {
  it('renders counts, top companies and the low-data badge', () => {
    wrap(<SubfieldCard card={makeCard()} region="global" internshipOnly={false} />);

    expect(screen.getByLabelText('Quantum Error Correction market pulse')).toBeInTheDocument();
    expect(screen.getByTestId('active-postings')).toHaveTextContent('3');
    expect(screen.getByTestId('internship-postings')).toHaveTextContent('1');
    expect(screen.getByText('low data')).toBeInTheDocument();
    expect(screen.getByText('Riverlane, Alice & Bob')).toBeInTheDocument();
  });

  it('shows "tracking since" when new_this_week is null (single-day corpus)', () => {
    wrap(
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
    wrap(
      <SubfieldCard
        card={makeCard({ new_this_week: 5, tracking_since: '2026-10-01' })}
        region="global"
        internshipOnly={false}
      />,
    );

    expect(screen.getByTestId('new-this-week')).toHaveTextContent(/\+5 new this week/);
  });

  it('shows a no-data hint when nothing was captured yet', () => {
    wrap(
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
    wrap(
      <SubfieldCard
        card={makeCard({ low_data: false, active_postings: 12 })}
        region="global"
        internshipOnly={false}
      />,
    );

    expect(screen.queryByText('low data')).not.toBeInTheDocument();
  });

  it('renders skill bars when top_skills are present', () => {
    wrap(
      <SubfieldCard
        card={makeCard({
          top_skills: [
            { skill_id: 'python', name: 'Python', share: 0.8 },
            { skill_id: 'qiskit', name: 'Qiskit', share: 0.5 },
          ],
        })}
        region="global"
        internshipOnly={false}
      />,
    );

    expect(screen.getByRole('list', { name: 'Skill shares list' })).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('renders research themes when themes are present', () => {
    wrap(
      <SubfieldCard
        card={makeCard({
          themes: [
            {
              label: 'Surface codes',
              summary: 'Focus on surface codes.',
              papers: [],
            },
          ],
        })}
        region="global"
        internshipOnly={false}
      />,
    );

    expect(screen.getByText('Surface codes')).toBeInTheDocument();
    expect(screen.getByText('Focus on surface codes.')).toBeInTheDocument();
  });
});
