/**
 * PostingList tests: loading skeleton, error message and the empty state
 * ("no postings captured yet — run a refresh") required by plan 1.6.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import * as pulseApi from '../api';
import { PostingList } from './PostingList';

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe('PostingList', () => {
  it('renders the loading skeleton while the query is in flight', () => {
    vi.spyOn(pulseApi, 'getPostings').mockReturnValue(new Promise(() => {}));

    render(<PostingList subfieldId="qec" region="global" internshipOnly={false} />, {
      wrapper: makeWrapper(),
    });

    expect(screen.getByRole('status', { name: /loading postings/i })).toBeInTheDocument();
  });

  it('renders an error state when the request fails', async () => {
    vi.spyOn(pulseApi, 'getPostings').mockRejectedValue(new Error('backend down'));

    render(<PostingList subfieldId="qec" region="global" internshipOnly={false} />, {
      wrapper: makeWrapper(),
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Could not load postings: backend down/,
    );
  });

  it('renders the empty state when no postings were captured', async () => {
    vi.spyOn(pulseApi, 'getPostings').mockResolvedValue({
      total: 0,
      limit: 10,
      offset: 0,
      items: [],
    });

    render(<PostingList subfieldId="qec" region="india" internshipOnly={false} />, {
      wrapper: makeWrapper(),
    });

    expect(
      await screen.findByText(/No postings captured yet — run a refresh\./),
    ).toBeInTheDocument();
  });

  it('renders postings with a safe apply link and the internship badge', async () => {
    vi.spyOn(pulseApi, 'getPostings').mockResolvedValue({
      total: 1,
      limit: 10,
      offset: 0,
      items: [
        {
          id: 7,
          title: 'QEC Intern',
          company: 'Riverlane',
          location: 'Cambridge, UK',
          via: 'LinkedIn',
          apply_url: 'https://example.com/apply/7',
          is_internship: true,
          first_seen_at: '2026-10-04T10:00:00Z',
          snippet: 'Work on decoders for quantum error correction.',
        },
      ],
    });

    render(<PostingList subfieldId="qec" region="global" internshipOnly={false} />, {
      wrapper: makeWrapper(),
    });

    const link = await screen.findByRole('link', { name: /Apply/ });
    expect(link).toHaveAttribute('href', 'https://example.com/apply/7');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText('internship')).toBeInTheDocument();
  });
});
