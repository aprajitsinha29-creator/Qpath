// Renders the India/Global region toggle as a radio group; changing the value
// must change the data request (query key includes region).
import type { PulseRegion } from '../../../types/api';

interface RegionToggleProps {
  value: PulseRegion;
  onChange: (region: PulseRegion) => void;
  disabled?: boolean;
}

const REGIONS: { value: PulseRegion; label: string }[] = [
  { value: 'global', label: 'Global' },
  { value: 'india', label: 'India' },
];

export function RegionToggle({ value, onChange, disabled = false }: RegionToggleProps) {
  return (
    <fieldset
      className="inline-flex rounded-lg border border-slate-800 bg-slate-900/60 p-0.5"
      disabled={disabled}
    >
      <legend className="sr-only">Data region</legend>
      {REGIONS.map((region) => (
        <button
          key={region.value}
          type="button"
          role="radio"
          aria-checked={value === region.value}
          onClick={() => onChange(region.value)}
          className={`rounded-md px-3 py-1 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500 ${
            value === region.value
              ? 'bg-cyan-950 text-cyan-300'
              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          {region.label}
        </button>
      ))}
    </fieldset>
  );
}
