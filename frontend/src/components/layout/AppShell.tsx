// Renders application shell with header navigation, health badge, and routed main content.
import { NavLink, Outlet } from 'react-router-dom';
import { HealthBadge } from '../../features/health/components/HealthBadge';

export function AppShell() {
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
                <span className="font-semibold tracking-tight text-white">Quantum Pathfinder</span>
                <span className="ml-2 rounded-sm bg-cyan-950 px-1.5 py-0.5 text-[10px] font-mono font-medium text-cyan-400 border border-cyan-800/60">
                  Phase 0
                </span>
              </div>
            </NavLink>

            {/* Navigation items per BUILD_PLAN.md 0.6.3 */}
            <nav className="flex items-center gap-2" aria-label="Main Navigation">
              <NavLink to="/" end className={navLinkClasses}>
                Pulse
              </NavLink>

              <div
                className="group relative inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-500 cursor-not-allowed select-none"
                aria-disabled="true"
                tabIndex={-1}
              >
                <span>Diagnostic</span>
                <span className="rounded-full bg-slate-800/80 border border-slate-700/60 px-1.5 py-0.2 text-[10px] font-normal text-slate-400">
                  coming soon
                </span>
              </div>

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
            Quantum Pathfinder — Live-data career navigator for quantum computing. Powered by
            SerpApi and Gemini.
          </p>
        </div>
      </footer>
    </div>
  );
}
