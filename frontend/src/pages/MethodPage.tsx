// Renders Methodology & Data Sources information page (Phase 7 placeholder).
export function MethodPage() {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 shadow-xl">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Data & Methodology
        </h1>
        <p className="mt-3 text-slate-300">
          Quantum Pathfinder grounds career navigation in real market data gathered through SerpApi
          (Google Jobs and Google Scholar) and structured intelligence extracted with Gemini.
        </p>
        <div className="mt-6 rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs font-mono text-slate-400 space-y-2">
          <p className="text-cyan-400 font-medium">Core principles:</p>
          <p>
            1. Deterministic scoring: All scores and ranks use pure formulas; AI never decides
            numbers.
          </p>
          <p>
            2. Honest limits: Sampled posting counts are clearly indicated with low-data badges.
          </p>
          <p>
            3. Controlled vocabulary: AI skill extraction maps only to predefined taxonomy
            identifiers.
          </p>
        </div>
      </div>
    </div>
  );
}
