import { useEffect, useRef, useState } from "react";

const INITIAL = { freshness: 0.3, authority: 0.25, owner: 0.2, country: 0.25 };
const SLIDERS = [
  ["freshness", "Fraîcheur"],
  ["authority", "Autorité"],
  ["owner", "Propriétaire"],
  ["country", "Pays"],
];

/** Ajuste les poids et relance une recherche après 400 ms de pause.
 * @param {{onRecalculate: (weights: object) => Promise<object>, initialWeights?: object}} props
 */
export default function WeightSliders({ onRecalculate, initialWeights = INITIAL, initialWinner = null }) {
  const [weights, setWeights] = useState(() => ({ ...INITIAL, ...initialWeights }));
  const [message, setMessage] = useState("");
  const [revision, setRevision] = useState(0);
  const timer = useRef(null);
  const lastWinner = useRef(initialWinner);

  useEffect(() => {
    if (revision === 0) return undefined;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      setMessage("");
      try {
        const result = await onRecalculate(weights);
        const next = result?.branches?.[0]?.value;
        if (lastWinner.current !== null && next === lastWinner.current) {
          setMessage("Résultat stable : la version dominante ne change pas avec ces poids.");
        }
        lastWinner.current = next ?? null;
      } catch {
        setMessage("Le classement n’a pas pu être recalculé.");
      }
    }, 400);
    return () => window.clearTimeout(timer.current);
  }, [revision, weights, onRecalculate]);

  function update(key, value) {
    setWeights((current) => ({ ...current, [key]: Number(value) }));
    setRevision((current) => current + 1);
  }

  function reset() {
    window.clearTimeout(timer.current);
    setWeights({ ...INITIAL });
    setRevision((current) => current + 1);
    setMessage("");
  }

  return (
    <section aria-labelledby="weights-heading" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Explorer le classement</p>
          <h2 className="mt-1 font-semibold text-ink" id="weights-heading">Poids des critères</h2>
        </div>
        <button className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50" onClick={reset} type="button">Réinitialiser</button>
      </div>
      <div className="mt-4 space-y-4">
        {SLIDERS.map(([key, label]) => (
          <div key={key}>
            <div className="mb-1 flex justify-between text-xs"><label className="font-medium text-ink" htmlFor={`weight-${key}`}>{label}</label><output htmlFor={`weight-${key}`} className="tabular-nums text-slate-500">{Math.round(weights[key] * 100)} %</output></div>
            <input aria-label={`Poids ${label}`} className="w-full accent-emerald-700" id={`weight-${key}`} max="1" min="0" onChange={(event) => update(key, event.target.value)} step="0.05" type="range" value={weights[key]} />
          </div>
        ))}
      </div>
      {message ? <p className="mt-3 text-xs text-slate-600" role="status">{message}</p> : null}
      <p className="mt-3 text-xs leading-5 text-slate-500">Les poids sont normalisés par le serveur ; vos réglages ne modifient pas les documents.</p>
    </section>
  );
}
