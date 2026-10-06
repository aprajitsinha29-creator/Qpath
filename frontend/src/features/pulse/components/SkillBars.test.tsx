/** SkillBars: renders shares, empty state, and coverage note. */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { SkillShare } from '../../../types/api';
import { SkillBars } from './SkillBars';

const SKILLS: SkillShare[] = [
  { skill_id: 'python', name: 'Python', share: 1.0 },
  { skill_id: 'qiskit', name: 'Qiskit', share: 0.5 },
];

describe('SkillBars', () => {
  it('renders skill names and percentage text for each skill', () => {
    render(<SkillBars skills={SKILLS} />);

    expect(screen.getByRole('list', { name: 'Skill shares list' })).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByText('Qiskit')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('shows the empty-state message when skills list is empty', () => {
    render(<SkillBars skills={[]} />);

    expect(screen.getByText(/No skills extracted yet/i)).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Skill shares list' })).not.toBeInTheDocument();
  });

  it('shows an extraction-coverage note when coverage < 1', () => {
    render(<SkillBars skills={SKILLS} extractionCoverage={0.75} />);

    expect(screen.getByText(/Coverage: 75% of postings extracted/)).toBeInTheDocument();
  });

  it('does not show coverage note when coverage is 1.0', () => {
    render(<SkillBars skills={SKILLS} extractionCoverage={1.0} />);

    expect(screen.queryByText(/Coverage:/)).not.toBeInTheDocument();
  });
});
