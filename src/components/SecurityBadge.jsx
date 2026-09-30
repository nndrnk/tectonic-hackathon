/** Bandeau discret décrivant la durée restante de la session.
 * @param {{role: string, seconds: number}} props
 */
export default function SecurityBadge({ role, seconds }) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = String(Math.floor(safeSeconds / 60)).padStart(2, "0");
  const remaining = String(safeSeconds % 60).padStart(2, "0");
  const roleLabel = { employee: "Employé", hr: "RH", payroll_expert: "Expert paie" }[role] || "Utilisateur";
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
      <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-trust-green" />Session limitée à votre rôle ({roleLabel})</span>
      <span aria-hidden="true">·</span><span>Données personnelles masquées</span>
      <span aria-hidden="true">·</span><span>Session expire dans {minutes}:{remaining}</span>
    </p>
  );
}
