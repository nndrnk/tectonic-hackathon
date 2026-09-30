import TrustGauge from "./TrustGauge.jsx";

const STATUS_COPY = {
  confident: { label: "Confiant", heading: "Réponse étayée", tone: "bg-emerald-100 text-emerald-900" },
  conflict: { label: "Contradiction", heading: "Les sources se contredisent", tone: "bg-amber-100 text-amber-950" },
  low: { label: "À vérifier", heading: "Pas assez d’informations fiables", tone: "bg-rose-100 text-rose-900" },
};

function explanationFor(result) {
  const branches = result.branches || [];
  const lead = branches[0];
  const independent = lead?.sources?.filter((source) => !source.is_duplicate && !source.suspicious).length || 0;
  let why;
  let missing;
  if (result.status === "confident") {
    why = `la branche principale est soutenue par ${independent} source${independent > 1 ? "s" : ""} indépendante${independent > 1 ? "s" : ""}.`;
    missing = "une confirmation indépendante supplémentaire renforcerait encore cette conclusion.";
  } else if (result.status === "conflict") {
    why = `${branches.length} versions différentes apparaissent dans les sources ; la première ne représente que ${Math.round(result.confidence)} % du poids comparé.`;
    missing = result.suggested_expert ? `un arbitrage de ${result.suggested_expert.name} aiderait à résoudre la contradiction.` : "une source officielle qui tranche entre ces versions fait défaut.";
  } else {
    why = "aucune branche ne dépasse le seuil de fiabilité défini pour une réponse étayée.";
    missing = "des sources plus récentes, plus fiables ou validées par un expert sont nécessaires.";
  }
  return `Pourquoi : ${why} Ce qui manque : ${missing}`;
}

/** Résumé de réponse, toujours accompagné de la raison et des éléments manquants.
 * @param {{result: object}} props
 */
export default function AnswerCard({ result }) {
  const copy = STATUS_COPY[result.status] || STATUS_COPY.low;
  return (
    <section aria-labelledby="answer-heading" aria-live="polite" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card sm:p-7">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <TrustGauge status={result.status} value={result.confidence} />
        <div className="min-w-0 flex-1">
          <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${copy.tone}`}>{copy.label}</span>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-ink" id="answer-heading">{copy.heading}</h2>
          {result.status === "confident" && result.answer ? (
            <p className="mt-2 text-lg leading-7 text-slate-700">{result.answer}</p>
          ) : (
            <p className="mt-2 text-sm leading-6 text-slate-600">Consultez les versions et les sources ci-dessous avant de prendre une décision.</p>
          )}
        </div>
      </div>
      <p className="mt-6 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">{explanationFor(result)}</p>
    </section>
  );
}
