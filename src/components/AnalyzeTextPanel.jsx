import { useEffect, useState } from "react";

/** Mode d'analyse permettant de coller un extrait sans le conserver après la session.
 * @param {{country: string, isLoading: boolean, onAnalyze: (request: {text: string, country: string}) => void}} props
 */
export default function AnalyzeTextPanel({ country, isLoading, onAnalyze }) {
  const [text, setText] = useState("");
  const [selectedCountry, setSelectedCountry] = useState(country);

  useEffect(() => setSelectedCountry(country), [country]);

  function submit(event) {
    event.preventDefault();
    const safeText = text.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "").trim();
    if (safeText.length < 20 || safeText.length > 5000 || isLoading) return;
    onAnalyze({ text: safeText, country: selectedCountry });
  }

  return (
    <details className="rounded-3xl border border-slate-200 bg-white shadow-card">
      <summary className="cursor-pointer list-none px-5 py-4 font-semibold text-ink marker:hidden sm:px-7">
        <span className="flex items-center justify-between gap-3">
          <span>Analyser un texte</span><span aria-hidden="true" className="text-slate-400">＋</span>
        </span>
        <span className="mt-1 block text-sm font-normal text-slate-500">Collez un extrait de politique ou de procédure pour l’examiner.</span>
      </summary>
      <form className="space-y-3 border-t border-slate-100 px-5 pb-5 pt-4 sm:px-7" onSubmit={submit}>
        <label className="sr-only" htmlFor="analyze-text">Texte à analyser</label>
        <textarea
          aria-describedby="analyze-help analyze-count"
          className="min-h-40 w-full resize-y rounded-xl border border-slate-300 px-4 py-3 text-sm leading-6 text-ink placeholder:text-slate-400"
          id="analyze-text"
          maxLength={5000}
          onChange={(event) => setText(event.target.value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, ""))}
          placeholder="Collez ici le passage à analyser…"
          value={text}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500" id="analyze-help">Évitez de coller des données personnelles réelles.</p>
          <p aria-live="polite" className="text-xs tabular-nums text-slate-500" id="analyze-count">{text.length}/5000 · minimum 20</p>
        </div>
        <div className="max-w-xs">
          <label className="mb-1.5 block text-sm font-medium text-ink" htmlFor="analyze-country">Pays concerné</label>
          <select className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-ink" id="analyze-country" onChange={(event) => setSelectedCountry(event.target.value)} value={selectedCountry}>
            <option value="BE">Belgique</option>
            <option value="FR">France</option>
            <option value="NL">Pays-Bas</option>
          </select>
        </div>
        <button className="rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50" disabled={isLoading || text.trim().length < 20} type="submit">
          {isLoading ? "Analyse…" : "Analyser ce texte"}
        </button>
      </form>
    </details>
  );
}
