import { useMemo, useState } from "react";
import DocumentDetail from "./DocumentDetail.jsx";

/** Liste de sources classées et panneau de détail au clic.
 * @param {{branches: object[], onVote: (docId: string, vote: "useful" | "wrong") => Promise<void>}} props
 */
export default function DocumentList({ branches, onVote, selectedSourceId, onSelectSource }) {
  const sources = useMemo(
    () => branches.flatMap((branch) => branch.sources.map((source) => ({ ...source, branchText: branch.claim_text })))
      .sort((left, right) => right.score - left.score),
    [branches],
  );
  const [internalSelectedId, setInternalSelectedId] = useState(sources[0]?.doc_id || null);
  const selectedId = selectedSourceId ?? internalSelectedId;
  const selected = sources.find((source) => source.doc_id === selectedId) || null;

  function selectSource(sourceId) {
    setInternalSelectedId(sourceId);
    onSelectSource?.(sourceId);
  }

  return (
    <section aria-labelledby="documents-heading" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card sm:p-7">
      <div className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Traçabilité</p>
        <h2 className="mt-1 text-xl font-semibold text-ink" id="documents-heading">Sources et calcul</h2>
      </div>
      {sources.length === 0 ? <p className="text-sm text-slate-600">Aucune source disponible pour cette recherche.</p> : (
        <div className="grid gap-5 lg:grid-cols-[minmax(220px,0.8fr)_minmax(0,1.2fr)]">
          <ul className="space-y-2" aria-label="Documents triés par score">
            {sources.map((source) => (
              <li key={`${source.doc_id}-${source.title}`}>
                <button
                  aria-current={selectedId === source.doc_id ? "true" : undefined}
                  className={`w-full rounded-xl border p-3 text-left transition ${selectedId === source.doc_id ? "border-trust-green bg-emerald-50" : "border-slate-200 hover:border-slate-400"} ${source.is_duplicate ? "opacity-65" : ""}`}
                  onClick={() => selectSource(source.doc_id)}
                  type="button"
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium leading-5 text-ink">{source.title}</span>
                    <span className="shrink-0 text-xs font-semibold tabular-nums text-slate-600">{Math.round(source.score * 100)}%</span>
                  </span>
                  <span className="mt-1 block text-xs text-slate-500">{source.is_duplicate ? "Copie · comptée 1 fois" : source.branchText}</span>
                  {source.suspicious ? <span className="mt-1 block text-xs font-medium text-trust-red">⚠ Contenu suspect</span> : null}
                </button>
              </li>
            ))}
          </ul>
          <DocumentDetail onVote={onVote} source={selected} />
        </div>
      )}
    </section>
  );
}
