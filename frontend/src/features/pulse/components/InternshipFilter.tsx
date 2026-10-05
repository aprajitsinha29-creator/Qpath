// Renders the internship-only filter checkbox; wired into the posting list
// request so toggling it changes the query.
interface InternshipFilterProps {
  value: boolean;
  onChange: (checked: boolean) => void;
}

export function InternshipFilter({ value, onChange }: InternshipFilterProps) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-300">
      <input
        type="checkbox"
        checked={value}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-2 focus:ring-cyan-500"
      />
      Internships only
    </label>
  );
}
