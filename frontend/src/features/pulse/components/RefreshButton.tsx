// Renders the dev-only Refresh button: asks for the admin token (kept in
// sessionStorage via lib/adminToken), posts to /admin/refresh/jobs and shows
// the run summary or the auth/validation error.
import { useState } from 'react';
import { clearAdminToken, getAdminToken, setAdminToken } from '../../../lib/adminToken';
import { useRefreshJobs } from '../hooks/usePulse';
import type { PulseRegion, RefreshMode } from '../../../types/api';

interface RefreshButtonProps {
  region: PulseRegion;
}

export function RefreshButton({ region }: RefreshButtonProps) {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState(getAdminToken());
  const [mode, setMode] = useState<RefreshMode>('bootstrap');
  const refresh = useRefreshJobs();

  const storedToken = getAdminToken();

  function runRefresh() {
    setAdminToken(token);
    refresh.mutate(
      { mode, region },
      {
        onSuccess: () => {
          setOpen(false);
        },
      },
    );
  }

  function signOut() {
    clearAdminToken();
    setToken('');
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((openState) => !openState)}
        className="rounded-lg border border-cyan-800/60 bg-cyan-950/40 px-3 py-1.5 text-sm font-medium text-cyan-300 transition-colors hover:bg-cyan-900/40 focus:outline-none focus:ring-2 focus:ring-cyan-500"
      >
        {refresh.isPending ? 'Refreshing…' : 'Refresh data'}
      </button>

      {refresh.isError ? (
        <p role="alert" className="mt-1 max-w-xs text-xs text-rose-300">
          Refresh failed: {refresh.error instanceof Error ? refresh.error.message : 'unknown error'}
        </p>
      ) : null}
      {refresh.isSuccess ? (
        <p role="status" className="mt-1 text-xs text-emerald-300">
          Last run: +{refresh.data.postings_new} new postings ({refresh.data.status})
        </p>
      ) : null}

      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-slate-700 bg-slate-900 p-4 shadow-2xl">
          <h3 className="text-sm font-semibold text-slate-100">Developer refresh</h3>
          <p className="mt-1 text-xs text-slate-400">
            Requires the admin token (dev-only; kept in this tab's sessionStorage).
          </p>

          <label
            htmlFor="admin-token-input"
            className="mt-3 block text-xs font-medium text-slate-300"
          >
            Admin token
          </label>
          <input
            id="admin-token-input"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder={storedToken ? '•••••• (stored)' : 'paste token'}
            autoComplete="off"
            className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />

          <fieldset className="mt-3">
            <legend className="text-xs font-medium text-slate-300">Mode</legend>
            <div className="mt-1 flex gap-3 text-xs text-slate-300">
              {(['bootstrap', 'daily'] as const).map((modeOption) => (
                <label key={modeOption} className="inline-flex items-center gap-1">
                  <input
                    type="radio"
                    name="refresh-mode"
                    checked={mode === modeOption}
                    onChange={() => setMode(modeOption)}
                    className="h-3.5 w-3.5 border-slate-700 bg-slate-950 text-cyan-500"
                  />
                  {modeOption}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="mt-4 flex items-center justify-between">
            {storedToken ? (
              <button
                type="button"
                onClick={signOut}
                className="text-xs text-slate-400 underline hover:text-slate-200"
              >
                Forget token
              </button>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={runRefresh}
              disabled={refresh.isPending || token.length === 0}
              className="rounded-md bg-cyan-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-cyan-600 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-cyan-400"
            >
              Run {mode} refresh
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
