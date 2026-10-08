// Renders the readiness radar chart (Recharts) with an interest overlay.
// Needs the scored subfields and the latest assessment scores/interests;
// a data table alternative keeps the chart accessible (AGENTS.md 3.6.6).
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { SubfieldOut } from '../../../types/api';

interface ReadinessRadarProps {
  subfields: SubfieldOut[];
  scores: Record<string, number>;
  interests: Record<string, number>;
}

/** Short axis label so six axes stay readable. */
function shortName(name: string): string {
  return name.length > 18 ? `${name.slice(0, 17)}…` : name;
}

export function ReadinessRadar({ subfields, scores, interests }: ReadinessRadarProps) {
  const data = subfields.map((s) => ({
    subfield: shortName(s.name),
    readiness: scores[s.id] ?? 0,
    interest: (interests[s.id] ?? 1) * 20, // slider 1-5 -> 20-100, same scale
  }));

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <h2 className="mb-2 text-lg font-semibold text-white">Readiness radar</h2>
      <div
        className="h-80 w-full"
        role="img"
        aria-label="Radar chart of readiness and interest per subfield; values follow in the table below"
      >
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="75%">
            <PolarGrid stroke="#334155" />
            <PolarAngleAxis dataKey="subfield" tick={{ fill: '#94a3b8', fontSize: 11 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} />
            <Radar
              name="Readiness"
              dataKey="readiness"
              stroke="#22d3ee"
              fill="#22d3ee"
              fillOpacity={0.35}
            />
            <Radar
              name="Interest"
              dataKey="interest"
              stroke="#a78bfa"
              fill="#a78bfa"
              fillOpacity={0.15}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      {/* Text alternative for the chart (AGENTS.md 3.6.6). */}
      <table className="mt-3 w-full text-left text-xs text-slate-300">
        <caption className="sr-only">Readiness and interest per subfield (0-100)</caption>
        <thead>
          <tr className="text-slate-400">
            <th scope="col" className="py-1 font-medium">
              Subfield
            </th>
            <th scope="col" className="py-1 font-medium">
              Readiness
            </th>
            <th scope="col" className="py-1 font-medium">
              Interest
            </th>
          </tr>
        </thead>
        <tbody>
          {subfields.map((s) => (
            <tr key={s.id} className="border-t border-slate-800">
              <td className="py-1">{s.name}</td>
              <td className="py-1 font-mono">{Math.round(scores[s.id] ?? 0)}</td>
              <td className="py-1 font-mono">{(interests[s.id] ?? 1) * 20}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
