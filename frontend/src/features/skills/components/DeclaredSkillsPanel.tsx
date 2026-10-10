// Collapsible panel wrapping SkillPicker on the paths page: holds the open
// state and the honest copy. Needs the profile id and its declared_skills.
import { useState } from 'react';
import { SkillPicker } from './SkillPicker';

interface DeclaredSkillsPanelProps {
  profileId: string;
  profileSkills: string[];
}

export function DeclaredSkillsPanel({ profileId, profileSkills }: DeclaredSkillsPanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <section
      aria-label="Declared skills"
      className="rounded-xl border border-slate-800 bg-slate-900/50"
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls="declared-skills-body"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left focus:outline-none focus:ring-2 focus:ring-cyan-500"
      >
        <span className="text-sm font-semibold text-white">
          Skills you already have <span className="font-normal text-slate-400">(optional)</span>
        </span>
        <span aria-hidden="true" className="text-slate-400">
          {open ? '▾' : '▸'}
        </span>
      </button>
      {open && (
        <div id="declared-skills-body" className="border-t border-slate-800">
          <SkillPicker profileId={profileId} profileSkills={profileSkills} />
        </div>
      )}
    </section>
  );
}
