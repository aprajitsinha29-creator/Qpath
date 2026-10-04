// Renders Market Pulse landing view with Phase 0 foundation placeholder card.
export function PulsePage() {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 shadow-xl backdrop-blur-sm">
        <div className="max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-md border border-cyan-800/40 bg-cyan-950/40 px-2.5 py-1 text-xs font-mono text-cyan-300">
            <span>●</span>
            <span>Phase 0: Foundation</span>
          </div>

          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Quantum Market Pulse
          </h1>

          <p className="text-base text-slate-300 leading-relaxed">
            Market Pulse provides live visibility into quantum computing job demand and research
            momentum across 6 subfields: Quantum Error Correction, Hardware Engineering, Quantum
            Software, Algorithms, Quantum ML, and Security & Networking.
          </p>

          <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 font-mono text-xs text-slate-400">
            <p className="text-cyan-400 font-semibold mb-1">Status check:</p>
            <p>• Backend API connected and healthy via GET /api/v1/health.</p>
            <p>• Reference taxonomy (7 subfields, 34 concepts, 53 skills) seeded in SQLite.</p>
            <p>
              • SerpApi fixture recording completed for offline testing and continuous development.
            </p>
            <p className="mt-2 text-slate-500">
              Market Pulse live cards and posting search arrive in Phase 1.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
