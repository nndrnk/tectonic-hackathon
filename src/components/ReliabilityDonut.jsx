import { Cell, Pie, PieChart } from "recharts";

/** Diagramme de répartition des documents fiables et des autres documents.
 * @param {{stats: {reliable_docs: number, total_docs: number, reliable_docs_pct: number}}} props
 */
export default function ReliabilityDonut({ stats }) {
  const reliable = Math.max(0, Number(stats.reliable_docs) || 0);
  const total = Math.max(0, Number(stats.total_docs) || 0);
  const other = Math.max(0, total - reliable);
  const data = [{ name: "Fiables", value: reliable }, { name: "Autres", value: other }];
  return (
    <section aria-labelledby="reliability-heading" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Qualité des sources</p>
      <h2 className="mt-1 font-semibold text-ink" id="reliability-heading">Documents fiables</h2>
      <div className="mt-3 flex items-center gap-2">
        <div aria-hidden="true" className="h-36 w-36 shrink-0">
          <PieChart className="trust-donut-chart" height={144} width={144}>
            <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={43} outerRadius={65} paddingAngle={total ? 3 : 0} stroke="none">
              <Cell fill="#147d64" />
              <Cell fill="#e2e8f0" />
            </Pie>
          </PieChart>
        </div>
        <div>
          <p className="text-3xl font-semibold tabular-nums text-ink">{Math.round(stats.reliable_docs_pct || 0)}%</p>
          <p className="text-xs text-slate-500">{reliable} sur {total} document{total === 1 ? "" : "s"} au-dessus de 60 %</p>
        </div>
      </div>
      <ul className="mt-2 flex gap-4 text-xs text-slate-600" aria-label="Légende">
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-trust-green" />Fiables</li>
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-slate-200" />Autres</li>
      </ul>
    </section>
  );
}
