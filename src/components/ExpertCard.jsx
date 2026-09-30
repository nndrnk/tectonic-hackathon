/** Expert suggéré pour aider à résoudre un conflit ou un manque de preuves.
 * @param {{expert: {name: string, team: string} | null}} props
 */
export default function ExpertCard({ expert }) {
  if (!expert) return null;
  return (
    <aside className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5" aria-label="Expert suggéré">
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-lg">✦</span>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Pour approfondir</p>
          <p className="mt-1 font-semibold text-ink">{expert.name}</p>
          <p className="text-sm text-slate-600">{expert.team}</p>
        </div>
      </div>
    </aside>
  );
}
