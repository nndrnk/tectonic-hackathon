import { useState } from "react";

const EXAMPLES = [
  { subject: "worker", label: "Travailleur", query: "Combien de jours de congé parental sont prévus en Belgique ?" },
  { subject: "worker", label: "Travailleur", query: "Comment sont remboursés les frais de transport ?" },
  { subject: "worker", label: "Travailleur", query: "Quel est le délai de préavis pour un contrat à durée indéterminée ?" },
  { subject: "group", label: "Groupe", query: "Quelle politique s’applique aux horaires flexibles pour une équipe ?" },
  { subject: "group", label: "Groupe", query: "Quelles règles communes encadrent le travail hybride ?" },
  { subject: "group", label: "Groupe", query: "Quels jours fériés s’appliquent à l’ensemble du personnel ?" },
];

/** Recherche avec filtres explicites et exemples adaptés au cas choisi.
 * @param {{onSearch: (request: {query: string, country: string, subject: string}) => void, isLoading: boolean}} props
 */
export default function SearchBar({ onSearch, isLoading }) {
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("BE");
  const [subject, setSubject] = useState("worker");

  function submit(event) {
    event.preventDefault();
    const safeQuery = query.replace(/[\u0000-\u001f\u007f]/g, "").trim();
    if (safeQuery.length < 3 || safeQuery.length > 300 || isLoading) return;
    onSearch({ query: safeQuery, country, subject });
  }

  function chooseExample(example) {
    setQuery(example.query);
    setSubject(example.subject);
  }

  return (
    <section aria-labelledby="search-heading" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card sm:p-7">
      <div className="mb-5">
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-trust-green">Recherche fiable</p>
        <h2 className="text-xl font-semibold tracking-tight text-ink" id="search-heading">
          Quelle information cherchez-vous ?
        </h2>
      </div>

      <form className="space-y-4" onSubmit={submit}>
        <div>
          <label className="sr-only" htmlFor="trustlens-query">Votre question</label>
          <textarea
            className="min-h-24 w-full resize-y rounded-2xl border border-slate-300 px-4 py-3 text-ink placeholder:text-slate-400"
            id="trustlens-query"
            maxLength={300}
            minLength={3}
            onChange={(event) => setQuery(event.target.value.replace(/[\u0000-\u001f\u007f]/g, ""))}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Posez une question sur une politique ou une procédure…"
            required
            rows={3}
            value={query}
          />
          <p className="mt-1 text-right text-xs text-slate-500" aria-live="polite">
            {query.length}/300 caractères
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-[1fr_1.4fr_auto] sm:items-end">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink" htmlFor="search-country">Pays</label>
            <select
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-ink"
              id="search-country"
              onChange={(event) => setCountry(event.target.value)}
              value={country}
            >
              <option value="BE">Belgique</option>
              <option value="FR">France</option>
              <option value="NL">Pays-Bas</option>
            </select>
          </div>
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-ink">Cas concerné</legend>
            <div className="flex rounded-xl border border-slate-300 p-1">
              {[
                ["worker", "Un travailleur"],
                ["group", "Un groupe"],
              ].map(([value, label]) => (
                <label
                  className={`flex-1 cursor-pointer rounded-lg px-3 py-2 text-center text-sm font-medium transition ${
                    subject === value ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100"
                  }`}
                  key={value}
                >
                  <input
                    checked={subject === value}
                    className="sr-only"
                    name="subject"
                    onChange={() => setSubject(value)}
                    type="radio"
                    value={value}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <button
            className="rounded-xl bg-trust-green px-5 py-3 font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isLoading || query.trim().length < 3}
            type="submit"
          >
            {isLoading ? "Recherche…" : "Rechercher"}
          </button>
        </div>
      </form>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Exemples à essayer</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.filter((example) => example.subject === subject).map((example) => (
            <button
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs text-slate-700 transition hover:border-trust-green hover:bg-emerald-50"
              key={example.query}
              onClick={() => chooseExample(example)}
              type="button"
            >
              {example.query}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
