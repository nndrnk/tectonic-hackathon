/** Affiche les avertissements comme du texte non fiable, jamais comme du HTML.
 * @param {{warnings: string[]}} props
 */
export default function WarningsBanner({ warnings = [] }) {
  if (warnings.length === 0) return null;
  return (
    <section aria-labelledby="warnings-title" className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
      <h2 className="flex items-center gap-2 font-semibold text-amber-950" id="warnings-title">
        <span aria-hidden="true">⚠</span> Points à vérifier
      </h2>
      <ul className="mt-3 space-y-2 text-sm leading-5 text-amber-900">
        {warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}
      </ul>
    </section>
  );
}
