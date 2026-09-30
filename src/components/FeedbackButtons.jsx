import { useState } from "react";

/** Retour utile/faux lié à une source ; le vote ne modifie pas le score affiché.
 * @param {{docId: string, onVote: (docId: string, vote: "useful" | "wrong") => Promise<void>}} props
 */
export default function FeedbackButtons({ docId, onVote }) {
  const [vote, setVote] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(value) {
    if (vote || busy) return;
    setBusy(true);
    setError("");
    try {
      await onVote(docId, value);
      setVote(value);
    } catch {
      setError("Retour non envoyé. Vous pouvez réessayer.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <p className="mb-2 text-xs font-medium text-slate-600">Cette source vous a-t-elle aidé ?</p>
      <div className="flex gap-2">
        <button aria-pressed={vote === "useful"} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50" disabled={busy || Boolean(vote)} onClick={() => send("useful")} type="button">
          {vote === "useful" ? "Merci · Utile" : "Utile"}
        </button>
        <button aria-pressed={vote === "wrong"} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50" disabled={busy || Boolean(vote)} onClick={() => send("wrong")} type="button">
          {vote === "wrong" ? "Merci · Faux" : "Faux"}
        </button>
      </div>
      {error ? <p className="mt-2 text-xs text-trust-red" role="alert">{error}</p> : null}
    </div>
  );
}
