/** Jauge circulaire SVG de la confiance générale.
 * @param {{value: number, status: string}} props
 */
export default function TrustGauge({ value, status }) {
  const safeValue = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
  const radius = 39;
  const circumference = 2 * Math.PI * radius;
  const color = status === "confident" ? "#147d64" : status === "conflict" ? "#b86612" : "#b83b4b";
  return (
    <div aria-label={`Confiance : ${Math.round(safeValue)} %`} className="relative grid h-28 w-28 shrink-0 place-items-center" role="img">
      <svg aria-hidden="true" className="h-full w-full -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" fill="none" r={radius} stroke="#e2e8f0" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          fill="none"
          r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - safeValue / 100)}
          strokeLinecap="round"
          strokeWidth="8"
        />
      </svg>
      <span className="absolute text-2xl font-semibold tracking-tight text-ink">{Math.round(safeValue)}<span className="text-sm">%</span></span>
    </div>
  );
}
