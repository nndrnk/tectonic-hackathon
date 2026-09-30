/** Décompte des sources indépendantes et des copies pour chaque branche.
 * @param {{branches: object[], onSelectSource: (source: object) => void}} props
 */
export default function CorroborationPanel({ branches, onSelectSource }) {
  return (
    <section aria-labelledby="corroboration-heading" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card sm:p-7">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Recoupement</p>
      <h2 className="mt-1 text-xl font-semibold text-ink" id="corroboration-heading">Qui soutient chaque version ?</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {branches.map((branch) => {
          const duplicates = branch.sources.filter((source) => source.is_duplicate).length;
          const independent = branch.sources.length - duplicates;
          return (
            <article className="rounded-2xl border border-slate-200 p-4" key={branch.value}>
              <p className="font-medium leading-6 text-ink">{branch.claim_text}</p>
              <p className="mt-2 text-xs text-slate-500">{independent} source{independent === 1 ? "" : "s"} indépendante{independent === 1 ? "" : "s"} · {duplicates} copie{duplicates === 1 ? "" : "s"} ignorée{duplicates === 1 ? "" : "s"} dans le score</p>
              <ul className="mt-3 space-y-1">
                {branch.sources.map((source) => (
                  <li key={source.doc_id}>
                    <button className="text-left text-sm text-trust-green underline decoration-emerald-200 underline-offset-2 hover:decoration-trust-green" onClick={() => onSelectSource(source)} type="button">
                      {source.title}{source.is_duplicate ? " · copie" : ""}
                    </button>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>
    </section>
  );
}
