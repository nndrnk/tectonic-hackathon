import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

/** Comparaison de toutes les versions en présence.
 * @param {{branches: object[]}} props
 */
export default function BranchBars({ branches }) {
  const data = branches.map((branch, index) => ({
    name: `Version ${index + 1}`,
    detail: branch.claim_text,
    confidence: Math.round(branch.share),
  }));
  return (
    <section aria-labelledby="branch-bars-heading" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Comparaison</p>
      <h2 className="mt-1 font-semibold text-ink" id="branch-bars-heading">Poids des versions</h2>
      {data.length === 0 ? <p className="mt-5 text-sm text-slate-500">Aucune branche à comparer.</p> : (
        <>
          <div aria-hidden="true" className="mt-4 overflow-x-auto">
            <BarChart className="trust-branch-chart" data={data} height={Math.max(150, data.length * 55)} layout="vertical" margin={{ left: 10, right: 20, top: 5, bottom: 5 }} width={400}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" horizontal={false} />
              <XAxis domain={[0, 100]} type="number" />
              <YAxis dataKey="name" type="category" width={82} />
              <Bar dataKey="confidence" fill="#147d64" radius={[0, 6, 6, 0]} />
            </BarChart>
          </div>
          <ol className="sr-only">
            {data.map((item) => <li key={item.name}>{item.name} : {item.confidence} %, {item.detail}</li>)}
          </ol>
        </>
      )}
    </section>
  );
}
