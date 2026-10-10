// Renders a searchable multi-select for the skills vocabulary with removable
// chips, a Save button, and an aria-live selection count. Needs the GET /skills
// vocabulary query, the profile's declared_skills to pre-fill, and the save
// mutation. Declaring skills does NOT change ranking — the copy must say so.
import { useMemo, useState } from 'react';
import { useSaveDeclaredSkills, useSkills } from '../hooks/useSkills';

interface SkillOption {
  id: string;
  /** searchable text: name + aliases (e.g. "mwpm" finds PyMatching) */
  haystack: string;
  name: string;
}

interface SkillPickerProps {
  profileId: string;
  profileSkills: string[];
}

export function SkillPicker({ profileId, profileSkills }: SkillPickerProps) {
  const { data, isLoading, isError, refetch } = useSkills();
  const saveMutation = useSaveDeclaredSkills(profileId);

  const [selected, setSelected] = useState<string[]>(profileSkills);
  const [query, setQuery] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  // Case-insensitive alphabetical display order (user spec): the backend
  // sorts by raw code points, so "C++" would land after "applied" names —
  // localeCompare with sensitivity 'base' keeps it stable and human.
  const options: SkillOption[] = useMemo(
    () =>
      (data ?? [])
        .map((skill) => ({
          id: skill.id,
          name: skill.name,
          haystack: `${skill.name} ${skill.aliases.join(' ')}`.toLowerCase(),
        }))
        .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })),
    [data],
  );

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((option) => option.haystack.includes(needle));
  }, [options, query]);

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-800/60 bg-red-950/30 p-4 text-sm text-red-300"
      >
        <p>Could not load the skills list.</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 rounded-md bg-red-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400"
        >
          Retry
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading skills vocabulary" className="space-y-2 p-4">
        <div className="h-9 animate-pulse rounded-md bg-slate-800/60" />
        <div className="h-24 animate-pulse rounded-md bg-slate-800/60" />
      </div>
    );
  }

  const toggle = (id: string) => {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
    setConfirmed(false);
  };

  const handleSave = () => {
    saveMutation.mutate(selected, { onSuccess: () => setConfirmed(true) });
  };

  return (
    <div className="space-y-3 p-4">
      <label htmlFor="skill-search" className="block text-sm font-medium text-slate-200">
        Search skills
      </label>
      <input
        id="skill-search"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="e.g. python, mwpm, qec"
        className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
      />

      <ul role="listbox" aria-label="Skills options" className="max-h-64 space-y-1 overflow-y-auto">
        {visible.length === 0 && (
          <li role="option" aria-selected={false} className="px-3 py-2 text-sm text-slate-500">
            No skills match that search.
          </li>
        )}
        {visible.map((option) => {
          const isSelected = selected.includes(option.id);
          return (
            <li key={option.id} role="option" aria-selected={isSelected}>
              <button
                type="button"
                role="checkbox"
                aria-checked={isSelected}
                aria-label={`${option.name} ${isSelected ? 'selected' : 'not selected'}`}
                onClick={() => toggle(option.id)}
                onKeyDown={(event) => {
                  if (event.key === ' ' || event.key === 'Enter') {
                    event.preventDefault();
                    toggle(option.id);
                  }
                }}
                className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 ${
                  isSelected ? 'bg-cyan-900/50 text-white' : 'bg-slate-900/60 text-slate-300'
                } hover:bg-slate-800`}
              >
                <span>{option.name}</span>
                {isSelected && <span aria-hidden="true">✓</span>}
              </button>
            </li>
          );
        })}
      </ul>

      <p aria-live="polite" role="status" className="text-xs text-slate-400">
        {selected.length} skill{selected.length === 1 ? '' : 's'} selected
      </p>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((id) => {
            const skill = options.find((option) => option.id === id);
            const name = skill?.name ?? id;
            return (
              <span
                key={id}
                className="inline-flex items-center gap-1 rounded-full bg-cyan-800/60 px-3 py-1 text-xs font-medium text-cyan-100"
              >
                {name}
                <button
                  type="button"
                  aria-label={`Remove ${name}`}
                  onClick={() => toggle(id)}
                  className="rounded-full px-1 text-cyan-200 hover:bg-cyan-700 hover:text-white focus:outline-none focus:ring-2 focus:ring-cyan-400"
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-cyan-400"
        >
          {saveMutation.isPending ? 'Saving…' : 'Save skills'}
        </button>
        {confirmed && !saveMutation.isPending && (
          <span role="status" className="text-xs text-emerald-400">
            Skills saved to your profile — they don't change the path ranking.
          </span>
        )}
        {saveMutation.isError && (
          <span role="alert" className="text-xs text-red-400">
            {saveMutation.error.message}
          </span>
        )}
      </div>

      <p className="text-xs text-slate-500">
        Saved to your profile only — the path ranking is computed from the market data and your
        diagnostic, never from this list.
      </p>
    </div>
  );
}
