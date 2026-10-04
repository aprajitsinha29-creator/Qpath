// Renders backend service health badge, querying GET /health via TanStack Query.
import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../api';

export function HealthBadge() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div
        role="status"
        aria-label="Checking backend status"
        className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-medium text-slate-400"
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
        </span>
        <span>Checking backend...</span>
      </div>
    );
  }

  if (isError || !data || data.status !== 'ok' || data.db !== 'ok') {
    return (
      <div
        role="status"
        aria-label="Backend status unreachable"
        className="inline-flex items-center gap-2 rounded-full border border-rose-800/60 bg-rose-950/60 px-3 py-1 text-xs font-medium text-rose-300"
      >
        <span className="h-2 w-2 rounded-full bg-rose-500" />
        <span>Backend: unreachable</span>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-label="Backend status OK"
      title={`Version: ${data.version} | Env: ${data.env} | DB: ${data.db}`}
      className="inline-flex items-center gap-2 rounded-full border border-emerald-800/60 bg-emerald-950/60 px-3 py-1 text-xs font-medium text-emerald-300"
    >
      <span className="relative flex h-2 w-2">
        <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
      </span>
      <span>Backend: OK</span>
    </div>
  );
}
