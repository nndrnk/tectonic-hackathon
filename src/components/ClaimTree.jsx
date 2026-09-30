/** Arbre lisible des branches, feuilles et copies.
 * @param {{query: string, branches: object[], onSelectSource: (source: object) => void}} props
 */
export default function ClaimTree({ query, branches, onSelectSource }) {
  return (
    <section aria-labelledby="tree-heading" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card sm:p-7">
      <div className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vue d’ensemble</p>
        <h2 className="mt-1 text-xl font-semibold text-ink" id="tree-heading">Arbre des affirmations</h2>
      </div>
      <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-ink">{query || "Question analysée"}</div>
      {branches.length === 0 ? <p className="mt-4 text-sm text-slate-500">Aucune branche n’a été extraite.</p> : (
        <ol className="mt-3 space-y-3">
          {branches.map((branch) => (
            <li className="border-l-2 border-slate-200 pl-4" key={branch.value}>
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white py-2">
                <p className="font-medium leading-6 text-ink">{branch.claim_text}</p>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${branch.score > 0.6 ? "bg-emerald-100 text-emerald-900" : branch.score > 0.4 ? "bg-amber-100 text-amber-900" : "bg-rose-100 text-rose-900"}`}>
                  {Math.round(branch.share)} % de confiance
                </span>
              </div>
              <ul className="mt-1 space-y-1.5">
                {branch.sources.map((source) => (
                  <li className={`ml-3 border-l border-slate-200 pl-3 ${source.is_duplicate ? "opacity-55" : ""}`} key={`${branch.value}-${source.doc_id}`}>
                    <button className="flex w-full flex-wrap items-center gap-x-2 gap-y-1 py-1 text-left text-sm text-slate-700 hover:text-trust-green" onClick={() => onSelectSource(source)} type="button">
                      <span aria-hidden="true">{source.suspicious ? "⚠" : "↳"}</span>
                      <span>{source.title}</span>
                      <span className="text-xs tabular-nums text-slate-500">{Math.round(source.score * 100)}%</span>
                      {source.is_duplicate ? <span className="text-xs text-slate-500">copie (comptée 1 fois)</span> : null}
                      {source.suspicious ? <span className="text-xs font-semibold text-trust-red">suspect</span> : null}
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
