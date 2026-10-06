/** ResearchFocus: renders themes, expandable papers, and empty state. */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ThemeOut } from '../../../types/api';
import { ResearchFocus } from './ResearchFocus';

const THEMES: ThemeOut[] = [
  {
    label: 'Surface codes',
    summary: 'Focus on surface codes for QEC.',
    papers: [
      { id: 1, title: 'Surface code paper', link: 'https://example.com/1' },
      { id: 2, title: 'Paper with no link', link: null },
    ],
  },
  {
    label: 'Decoders',
    summary: 'MWPM and union-find decoders.',
    papers: [],
  },
];

describe('ResearchFocus', () => {
  it('renders theme labels and summaries', () => {
    render(<ResearchFocus themes={THEMES} />);

    expect(screen.getByText('Surface codes')).toBeInTheDocument();
    expect(screen.getByText('Focus on surface codes for QEC.')).toBeInTheDocument();
    expect(screen.getByText('Decoders')).toBeInTheDocument();
  });

  it('shows the empty-state message when no themes', () => {
    render(<ResearchFocus themes={[]} />);

    expect(screen.getByText(/No research themes yet/i)).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('expands paper list when the papers button is clicked', () => {
    render(<ResearchFocus themes={THEMES} />);

    // Papers initially hidden
    expect(screen.queryByText('Surface code paper')).not.toBeInTheDocument();

    // Click the expand button for the first theme
    const btn = screen.getByRole('button', { name: /2 papers/i });
    fireEvent.click(btn);

    expect(screen.getByText('Surface code paper')).toBeInTheDocument();
    // Paper link opens in a new tab
    const link = screen.getByRole('link', { name: 'Surface code paper' });
    expect(link).toHaveAttribute('href', 'https://example.com/1');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    // Paper without a link renders as plain text
    expect(screen.getByText('Paper with no link')).toBeInTheDocument();
  });

  it('collapses paper list when clicked again', () => {
    render(<ResearchFocus themes={THEMES} />);

    const btn = screen.getByRole('button', { name: /2 papers/i });
    fireEvent.click(btn);
    expect(screen.getByText('Surface code paper')).toBeInTheDocument();

    fireEvent.click(btn);
    expect(screen.queryByText('Surface code paper')).not.toBeInTheDocument();
  });

  it('does not show a papers button for themes with no papers', () => {
    render(<ResearchFocus themes={[THEMES[1]]} />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
