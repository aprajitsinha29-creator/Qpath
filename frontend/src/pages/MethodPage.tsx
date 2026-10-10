// Renders the Data & Methodology page (plan 7): the verbatim
// docs/DATA_AND_METHOD.md sections plus a "Live numbers" block from
// GET /meta/method (loading, error, and empty states included). Needs the
// meta/method query only; document sections are static content.
import { LiveNumbers } from '../features/meta/components/LiveNumbers';
import { DATA_AND_METHOD_SECTIONS, MethodDocSection } from '../features/meta/components/MethodDoc';
import { useMethodStats } from '../features/meta/hooks/useMeta';

export function MethodPage() {
  const stats = useMethodStats();

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Data &amp; Methodology
        </h1>
        <p className="text-sm text-slate-400">
          Where our market data comes from, what the AI is allowed to do, and the numbers behind
          this instance — stated honestly.
        </p>
      </header>

      {/* Document sections: verbatim text from docs/DATA_AND_METHOD.md. */}
      <div className="space-y-8 rounded-xl border border-slate-800 bg-slate-900/50 p-6">
        {DATA_AND_METHOD_SECTIONS.map((section) => (
          <MethodDocSection key={section.title} section={section} />
        ))}
      </div>

      {/* Live numbers from the backend (facts, not derived claims). */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
        <LiveNumbers
          data={stats.data}
          isLoading={stats.isLoading}
          isError={stats.isError}
          onRetry={() => stats.refetch()}
        />
      </div>
    </div>
  );
}
