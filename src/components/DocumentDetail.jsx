import FeedbackButtons from "./FeedbackButtons.jsx";

const FACTORS = [
  ["freshness", "Fraîcheur", "Plus le document est récent, plus cette valeur est élevée."],
  ["authority", "Autorité", "Le type de source détermine son niveau d’autorité."],
  ["owner", "Propriétaire", "La présence d’un propriétaire identifié renforce la traçabilité."],
  ["country", "Pays", "La valeur est élevée si le pays correspond à la recherche."],
];

/** Détail transparent d'une source sélectionnée.
 * @param {{source: object | null, onVote: (docId: string, vote: "useful" | "wrong") => Promise<void>}} props
 */
export default function DocumentDetail({ source, onVote }) {
  if (!source) {
    return <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Sélectionnez une source pour voir son calcul et sa citation.</div>;
  }

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Détail de la source</p>
          <h3 className="mt-1 text-lg font-semibold text-ink">{source.title}</h3>
          <p className="mt-1 text-xs text-slate-500">Référence {source.doc_id}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-semibold text-ink">Score {Math.round(source.score * 100)} %</span>
      </div>

      <div className="mt-5 space-y-4">
        {FACTORS.map(([key, label, explanation]) => {
          const value = Math.max(0, Math.min(1, Number(source.breakdown?.[key]) || 0));
          return (
            <div key={key}>
              <div className="mb-1 flex justify-between gap-3 text-xs">
                <span className="font-semibold text-ink">{label}</span><span className="tabular-nums text-slate-600">{Math.round(value * 100)} %</span>
              </div>
              <progress aria-label={`${label} : ${Math.round(value * 100)} %`} className="trust-progress block h-2 w-full overflow-hidden rounded-full" max="1" value={value} />
              <p className="mt-1 text-xs leading-5 text-slate-500">{explanation}</p>
            </div>
          );
        })}
      </div>

      <blockquote className="mt-5 rounded-xl border-l-4 border-trust-green bg-emerald-50 px-4 py-3 text-sm leading-6 text-slate-700">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-trust-green">Citation exacte</p>
        <p>« {source.quote} »</p>
      </blockquote>

      <div className="mt-4 flex flex-wrap gap-2">
        {source.needs_review ? <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900">À vérifier</span> : null}
        {source.expiring_soon ? <span className="rounded-full bg-orange-100 px-2.5 py-1 text-xs font-medium text-orange-900">Expire bientôt</span> : null}
        {source.suspicious ? <span className="rounded-full bg-rose-100 px-2.5 py-1 text-xs font-medium text-rose-900">Contenu suspect</span> : null}
      </div>
      <FeedbackButtons docId={source.doc_id} onVote={onVote} />
    </article>
  );
}
