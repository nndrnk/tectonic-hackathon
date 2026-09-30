import { Component } from "react";

/** Frontière qui remplace un écran cassé par un message sans détails techniques. */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch() {
    // Les détails techniques restent dans les outils de développement, pas dans l'interface.
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="grid min-h-screen place-items-center bg-paper p-6">
          <section className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card" role="alert">
            <h1 className="text-xl font-semibold text-ink">Un problème est survenu</h1>
            <p className="mt-2 text-sm text-slate-600">Rechargez la page pour reprendre votre recherche.</p>
            <button className="mt-5 rounded-xl bg-ink px-4 py-2.5 font-medium text-white" onClick={() => window.location.reload()} type="button">
              Recharger
            </button>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}
