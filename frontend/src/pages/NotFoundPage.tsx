// Renders 404 Not Found error view.
import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-10 max-w-md shadow-2xl">
        <span className="font-mono text-4xl font-bold text-cyan-400">404</span>
        <h1 className="mt-4 text-xl font-semibold text-white">Page Not Found</h1>
        <p className="mt-2 text-sm text-slate-400">The requested path does not exist in QPath.</p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 focus:outline-hidden focus:ring-2 focus:ring-cyan-500"
        >
          Return to Market Pulse
        </Link>
      </div>
    </div>
  );
}
