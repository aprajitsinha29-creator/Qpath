// Renders the "Track this path" / "Tracking" button on a PathCard. Needs the
// path's id, the currently tracked path id (or null), and this card's tracked
// state comes from the mutation below. Switching paths is allowed (plan 5.5).
import { useSetChosenPath } from '../hooks/useTracker';

interface TrackPathButtonProps {
  profileId: string;
  pathId: string;
  /** The profile's currently tracked path id (null until tracked). */
  trackedPathId: string | null;
}

export function TrackPathButton({ profileId, pathId, trackedPathId }: TrackPathButtonProps) {
  const mutation = useSetChosenPath(profileId);
  const isTracked = trackedPathId === pathId;

  return (
    <button
      type="button"
      aria-pressed={isTracked}
      aria-label={isTracked ? `Tracking ${pathId}` : `Track ${pathId}`}
      onClick={() => mutation.mutate(pathId)}
      disabled={mutation.isPending}
      className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:cursor-not-allowed disabled:opacity-50 ${
        isTracked
          ? 'bg-emerald-700/70 text-emerald-100 hover:bg-emerald-600'
          : 'bg-slate-800 text-slate-200 hover:bg-slate-700'
      }`}
    >
      {mutation.isPending
        ? 'Tracking…'
        : isTracked
          ? 'Tracking ✓'
          : trackedPathId
            ? 'Switch to this path'
            : 'Track this path'}
    </button>
  );
}
