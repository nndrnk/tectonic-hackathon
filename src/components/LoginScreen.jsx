import { useState } from "react";

/** Écran de connexion sans persistance du jeton côté navigateur.
 * @param {{onLogin: (credentials: {username: string, password: string}) => Promise<void>, isSubmitting: boolean, error: string}} props
 */
export default function LoginScreen({ onLogin, isSubmitting, error }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    await onLogin({ username, password });
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-5 py-12">
      <section className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-card sm:p-10">
        <div className="mb-9 flex items-center gap-3">
          <div
            aria-hidden="true"
            className="grid h-12 w-12 place-items-center rounded-2xl bg-ink text-lg font-bold text-white"
          >
            TL
          </div>
          <div>
            <p className="text-xl font-semibold tracking-tight text-ink">TrustLens</p>
            <p className="text-sm text-slate-500">Des réponses que l’on peut vérifier</p>
          </div>
        </div>

        <div className="mb-7">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-trust-green">
            Accès sécurisé
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">Bienvenue</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Connectez-vous pour explorer les politiques, procédures et sources de votre organisation.
          </p>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-ink" htmlFor="username">
              Identifiant
            </label>
            <input
              autoComplete="username"
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-ink placeholder:text-slate-400"
              id="username"
              maxLength={32}
              minLength={3}
              onChange={(event) => setUsername(event.target.value.replace(/[\u0000-\u001f\u007f]/g, ""))}
              placeholder="Votre identifiant"
              required
              type="text"
              value={username}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-ink" htmlFor="password">
              Mot de passe
            </label>
            <input
              autoComplete="current-password"
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-ink placeholder:text-slate-400"
              id="password"
              maxLength={128}
              minLength={8}
              onChange={(event) => setPassword(event.target.value.replace(/[\u0000-\u001f\u007f]/g, ""))}
              placeholder="Au moins 8 caractères"
              required
              type="password"
              value={password}
            />
          </div>

          {error ? (
            <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-trust-red" role="alert">
              {error}
            </p>
          ) : null}

          <button
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-5 py-3.5 font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Connexion…" : "Se connecter"}
            {!isSubmitting ? <span aria-hidden="true">→</span> : null}
          </button>
        </form>

        <p className="mt-6 text-center text-xs leading-5 text-slate-500">
          Les identifiants sont transmis à l’API sécurisée et le jeton reste en mémoire pendant la session.
        </p>
      </section>
    </main>
  );
}
