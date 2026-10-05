/**
 * RegionToggle tests: the toggle must flip selection on click — the query key
 * includes region, so this is what drives a fresh request per region.
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RegionToggle } from './RegionToggle';

describe('RegionToggle', () => {
  it('marks the active region and fires onChange for the other one', () => {
    const onChange = vi.fn();
    render(<RegionToggle value="global" onChange={onChange} />);

    expect(screen.getByRole('radio', { name: 'Global' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('radio', { name: 'India' })).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(screen.getByRole('radio', { name: 'India' }));
    expect(onChange).toHaveBeenCalledWith('india');
  });
});
