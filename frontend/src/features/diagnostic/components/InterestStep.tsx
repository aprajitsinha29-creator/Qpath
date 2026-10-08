// Renders the interest step: one labeled 1-5 slider per scored subfield.
// Needs the scored subfields (id + name) and the current interest values.
import type { SubfieldOut } from '../../../types/api';

export const INTEREST_MIN = 1;
export const INTEREST_MAX = 5;

interface InterestStepProps {
  subfields: SubfieldOut[];
  interests: Record<string, number>;
  onChange: (subfieldId: string, value: number) => void;
}

export function InterestStep({ subfields, interests, onChange }: InterestStepProps) {
  return (
    <fieldset className="space-y-5">
      <legend className="text-lg font-semibold text-white">
        How interested are you in each area? (1 = not at all, 5 = very)
      </legend>
      {subfields.map((subfield) => (
        <div key={subfield.id} className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-baseline justify-between gap-4">
            <label htmlFor={`interest-${subfield.id}`} className="font-medium text-slate-100">
              {subfield.name}
            </label>
            <span className="font-mono text-sm text-cyan-300" aria-hidden="true">
              {interests[subfield.id] ?? INTEREST_MIN}/5
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">{subfield.description}</p>
          <input
            id={`interest-${subfield.id}`}
            type="range"
            min={INTEREST_MIN}
            max={INTEREST_MAX}
            step={1}
            value={interests[subfield.id] ?? INTEREST_MIN}
            onChange={(e) => onChange(subfield.id, Number(e.target.value))}
            aria-label={`Interest in ${subfield.name}, 1 to 5`}
            aria-valuetext={`${interests[subfield.id] ?? INTEREST_MIN} out of 5`}
            className="mt-3 w-full accent-cyan-500"
          />
        </div>
      ))}
    </fieldset>
  );
}
