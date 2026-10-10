/**
 * Shared formatting utilities for dates, numbers, and percentages (AGENTS.md 3.6.8).
 */

/**
 * Format a number with thousands separators.
 */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}

/**
 * Format a decimal fraction (0.0 to 1.0) or percentage as a readable string.
 */
export function formatPercent(value: number, decimals = 0): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format an ISO date or timestamp into a human-readable string.
 */ export function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return isoString;
    }
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(date);
  } catch {
    return isoString;
  }
}

/**
 * Format an ISO timestamp as a coarse relative time for status pills
 * ("3h ago", "2d ago", "just now"). Falls back to the raw string when
 * unparseable. Coarse granularity is deliberate: exact minutes would imply
 * precision the sampled data does not have.
 */
export function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return isoString;
    }
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 90) {
      return 'just now';
    }
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
      return `${minutes}m ago`;
    }
    const hours = Math.floor(minutes / 60);
    if (hours < 48) {
      return `${hours}h ago`;
    }
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return isoString;
  }
}
