/** MixChips: renders seniority chips, PhD share, and internship count. */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MixChips } from './MixChips';

describe('MixChips', () => {
  it('renders seniority chips for each non-zero bucket', () => {
    render(
      <MixChips
        seniorityMix={{ mid: 2, intern: 1, senior: 1, unknown: 1 }}
        phdShare={0.5}
        internshipPostings={1}
      />,
    );

    expect(screen.getByText(/Mid/)).toBeInTheDocument();
    expect(screen.getByText(/Intern/)).toBeInTheDocument();
    expect(screen.getByText(/^Senior\b/)).toBeInTheDocument();
    expect(screen.getByText(/Unspecified/)).toBeInTheDocument();
  });

  it('shows PhD share chip when phd_share is not null', () => {
    render(<MixChips seniorityMix={{ mid: 1 }} phdShare={0.33} internshipPostings={0} />);

    expect(screen.getByText(/PhD required: 33%/)).toBeInTheDocument();
  });

  it('does not render PhD chip when phd_share is null', () => {
    render(<MixChips seniorityMix={{ mid: 1 }} phdShare={null} internshipPostings={0} />);

    expect(screen.queryByText(/PhD required/)).not.toBeInTheDocument();
  });

  it('shows internship chip when count > 0', () => {
    render(<MixChips seniorityMix={{}} phdShare={null} internshipPostings={3} />);

    expect(screen.getByText(/3 internships/)).toBeInTheDocument();
  });

  it('shows empty seniority message when all counts are 0', () => {
    render(<MixChips seniorityMix={{ mid: 0 }} phdShare={null} internshipPostings={0} />);

    expect(screen.getByText(/No seniority data extracted yet/)).toBeInTheDocument();
  });
});
