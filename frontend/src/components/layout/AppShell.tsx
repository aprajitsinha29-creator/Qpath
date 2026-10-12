// Renders application shell with header navigation, health badge, and routed
// main content. The Opportunities nav item is enabled only once a path is
// tracked (plan 5.5); it reads GET /profiles/{id} via useChosenPath and
// renders a non-clickable hint otherwise.
import { NavLink, Outlet } from 'react-router-dom';
import { HealthBadge } from '../../features/health/components/HealthBadge';
import { useChosenPath } from '../../features/tracker/hooks/useTracker';
import { getOrCreateProfileId } from '../../lib/profileId';

export function AppShell() {
  const profileId = getOrCreateProfileId();
  const { data: chosenPath } = useChosenPath(profileId);
  const pathTracked = Boolean(chosenPath?.chosen_path_id);

  const navLinkClasses = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
    }`;

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      {/* Top Header */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-8">
            <NavLink
              to="/"
              className="flex items-center gap-2.5 focus:outline-hidden focus:ring-2 focus:ring-cyan-500"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 font-mono text-base font-bold text-white shadow-md shadow-cyan-900/40">
                Ψ
              </span>
              <div>
                <span className="font-semibold tracking-tight text-white">QPath</span>
              </div>
            </NavLink>

            {/* Navigation items per BUILD_PLAN.md 0.6.3; the Opportunities item
                is gated on a tracked path (plan 5.5). */}
            <nav className="flex items-center gap-2" aria-label="Main Navigation">
              <NavLink to="/" end className={navLinkClasses}>
                Pulse
              </NavLink>

              <NavLink to="/diagnostic" className={navLinkClasses}>
                Diagnostic
              </NavLink>

              <NavLink to="/paths" className={navLinkClasses}>
                Paths
              </NavLink>

              {pathTracked ? (
                <NavLink to="/opportunities" className={navLinkClasses}>
                  Opportunities
                </NavLink>
              ) : (
                // Gate: visible but not clickable until a path is tracked —
                // the hint keeps the route discoverable without promising data
                // the feed cannot compute yet (GET would 409 path_required).
                <span
                  data-testid="opportunities-nav-gate"
                  aria-disabled="true"
                  title="Track a path on the Paths page to unlock Opportunities"
                  className="cursor-not-allowed px-3 py-1.5 text-sm font-medium text-slate-600"
                >
                  Opportunities
                </span>
              )}

              <NavLink to="/method" className={navLinkClasses}>
                Method
              </NavLink>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <HealthBadge />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <p>
            QPath — Live-data career navigator for quantum computing. Powered by SerpApi and Gemini.
          </p>
        </div>
      </footer>
    </div>
  );
}
