// Renders a "Low data" notice when active_postings < 8 (plan 4.6).
// Explains that evidence is thin so the user isn't misled by the demand score.
export function LowDataNotice() {
  return (
    <p
      role="note"
      className="mt-1 rounded border border-amber-800/60 bg-amber-950/30 px-3 py-1.5 text-xs text-amber-300"
    >
      ⚠ Fewer than 8 active postings captured — demand evidence is thin. Scores may change as more
      data arrives.
    </p>
  );
}
