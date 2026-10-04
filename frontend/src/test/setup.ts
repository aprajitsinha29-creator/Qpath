/**
 * Vitest global test setup (AGENTS.md 3.7.4).
 *
 * Configures DOM matchers from @testing-library/jest-dom for Vitest.
 */

import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
