import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AnalyzeTextPanel from "./components/AnalyzeTextPanel.jsx";
import AnswerCard from "./components/AnswerCard.jsx";
import BranchBars from "./components/BranchBars.jsx";
import ClaimTree from "./components/ClaimTree.jsx";
import CorroborationPanel from "./components/CorroborationPanel.jsx";
import DocumentList from "./components/DocumentList.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import ExpertCard from "./components/ExpertCard.jsx";
import LoginScreen from "./components/LoginScreen.jsx";
import ReliabilityDonut from "./components/ReliabilityDonut.jsx";
import SearchBar from "./components/SearchBar.jsx";
import SecurityBadge from "./components/SecurityBadge.jsx";
import WarningsBanner from "./components/WarningsBanner.jsx";
import WeightSliders from "./components/WeightSliders.jsx";
import { analyzeText, getSessionSeconds, login, logout, search, sendFeedback } from "./api.js";

function LoadingSkeleton() {
  return (
    <div aria-label="Chargement des résultats" className="animate-pulse space-y-4" role="status">
      <div className="h-48 rounded-3xl bg-slate-200" />
      <div className="grid gap-4 md:grid-cols-3"><div className="h-56 rounded-3xl bg-slate-200" /><div className="h-56 rounded-3xl bg-slate-200 md:col-span-2" /></div>
    </div>
  );
}

function TrustLensApp() {
  const [session, setSession] = useState(null);
  const [sessionSeconds, setSessionSeconds] = useState(0);
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [result, setResult] = useState(null);
  const [currentQuery, setCurrentQuery] = useState("");
  const [lastSearch, setLastSearch] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState(null);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const loginLock = useRef(false);
  const requestController = useRef(null);
  const requestNumber = useRef(0);
  const lastSearchRef = useRef(null);

  const clearSession = useCallback(() => {
    requestNumber.current += 1;
    requestController.current?.abort();
    requestController.current = null;
    setSession(null);
    setSessionSeconds(0);
    setIsLoading(false);
    setResult(null);
    setLastSearch(null);
    lastSearchRef.current = null;
    setCurrentQuery("");
    setRequestError("");
    setFeedbackMessage("");
  }, []);

  useEffect(() => {
    window.addEventListener("trustlens:session-expired", clearSession);
    return () => window.removeEventListener("trustlens:session-expired", clearSession);
  }, [clearSession]);

  useEffect(() => {
    if (!session) return undefined;
    const timer = window.setInterval(() => {
      const remaining = getSessionSeconds();
      setSessionSeconds(remaining);
      if (remaining <= 0) logout();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [session]);

  async function handleLogin(credentials) {
    if (loginLock.current) return;
    loginLock.current = true;
    setIsLoggingIn(true);
    setLoginError("");
    try {
      const info = await login(credentials);
      setSession(info);
      setSessionSeconds(info.expires_in);
    } catch {
      setLoginError("Connexion impossible. Vérifiez vos identifiants et réessayez.");
    } finally {
      loginLock.current = false;
      setIsLoggingIn(false);
    }
  }

  const executeRequest = useCallback(async ({ payload, kind, preserveResult = false }) => {
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    const requestId = ++requestNumber.current;
    setIsLoading(true);
    setRequestError("");
    setFeedbackMessage("");
    if (!preserveResult) {
      setResult(null);
      setSelectedSourceId(null);
    }
    setCurrentQuery(kind === "search" ? payload.query : "Texte fourni à analyser");
    if (kind === "search") {
      lastSearchRef.current = payload;
      setLastSearch(payload);
    } else {
      lastSearchRef.current = null;
      setLastSearch(null);
    }
    try {
      const next = kind === "search"
        ? await search(payload, { signal: controller.signal })
        : await analyzeText(payload, { signal: controller.signal });
      if (requestId !== requestNumber.current) return null;
      setResult(next);
      setSelectedSourceId(next.branches?.[0]?.sources?.[0]?.doc_id || null);
      return next;
    } catch (error) {
      if (error?.name === "AbortError" || requestId !== requestNumber.current) return null;
      setRequestError(error instanceof Error ? error.message : "La demande n’a pas abouti. Réessayez.");
      return null;
    } finally {
      if (requestId === requestNumber.current) {
        requestController.current = null;
        setIsLoading(false);
      }
    }
  }, []);

  const handleSearch = useCallback((payload) => executeRequest({ payload, kind: "search" }), [executeRequest]);
  const handleAnalyze = useCallback((payload) => executeRequest({ payload, kind: "analyze" }), [executeRequest]);
  const handleRecalculate = useCallback(async (weights) => {
    const previous = lastSearchRef.current;
    if (!previous) return null;
    return executeRequest({ payload: { ...previous, weights }, kind: "search", preserveResult: true });
  }, [executeRequest]);

  const handleVote = useCallback(async (docId, vote) => {
    try {
      await sendFeedback(docId, vote);
      setFeedbackMessage("Merci, votre retour a été enregistré.");
    } catch {
      setFeedbackMessage("Votre retour n’a pas pu être envoyé. Réessayez.");
      throw new Error("Retour non envoyé.");
    }
  }, []);

  const allSources = useMemo(
    () => result?.branches?.flatMap((branch) => branch.sources) || [],
    [result],
  );
  const selectedSource = allSources.find((source) => source.doc_id === selectedSourceId);

  if (!session) return <LoginScreen error={loginError} isSubmitting={isLoggingIn} onLogin={handleLogin} />;

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4 lg:px-8">
          <a aria-label="TrustLens, accueil" className="flex items-center gap-3" href="#top">
            <span aria-hidden="true" className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-sm font-bold text-white">TL</span>
            <span><span className="block text-lg font-semibold leading-5">TrustLens</span><span className="text-xs text-slate-500">Recherche organisationnelle vérifiable</span></span>
          </a>
          <div className="flex flex-wrap items-center gap-4">
            <SecurityBadge role={session.role} seconds={sessionSeconds} />
            <button className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" onClick={logout} type="button">Se déconnecter</button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-5 py-8 lg:px-8 lg:py-10" id="top">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-trust-green">Transparence · Contradictions · Sécurité</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Trouvez l’information. Vérifiez pourquoi elle compte.</h1>
          <p className="mt-3 text-base leading-7 text-slate-600">TrustLens rapproche les sources et rend visible leur niveau de confiance, sans cacher les désaccords.</p>
        </div>

        <SearchBar isLoading={isLoading} onSearch={handleSearch} />
        <AnalyzeTextPanel country={lastSearch?.country || "BE"} isLoading={isLoading} onAnalyze={handleAnalyze} />
        {requestError ? <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-trust-red" role="alert">{requestError}</p> : null}
        {feedbackMessage ? <p className="text-sm text-slate-600" role="status">{feedbackMessage}</p> : null}

        {isLoading && !result ? <LoadingSkeleton /> : null}
        {result ? (
          <div aria-busy={isLoading} className="space-y-6">
            <AnswerCard result={result} />
            {result.status !== "confident" ? <ExpertCard expert={result.suggested_expert} /> : null}
            <div className="grid gap-4 lg:grid-cols-3">
              <ReliabilityDonut stats={result.stats} />
              <div className="lg:col-span-2"><BranchBars branches={result.branches} /></div>
            </div>
            {lastSearch ? (
              <WeightSliders
                initialWinner={result.branches?.[0]?.value || null}
                onRecalculate={handleRecalculate}
              />
            ) : null}
            <ClaimTree
              branches={result.branches}
              onSelectSource={(source) => setSelectedSourceId(source.doc_id)}
              query={currentQuery}
            />
            <CorroborationPanel
              branches={result.branches}
              onSelectSource={(source) => setSelectedSourceId(source.doc_id)}
            />
            <DocumentList
              branches={result.branches}
              onSelectSource={setSelectedSourceId}
              onVote={handleVote}
              selectedSourceId={selectedSourceId}
            />
            <WarningsBanner warnings={result.warnings} />
          </div>
        ) : !isLoading ? (
          <section className="rounded-3xl border border-dashed border-slate-300 bg-white/70 px-6 py-10 text-center">
            <span aria-hidden="true" className="text-3xl">⌕</span>
            <h2 className="mt-3 font-semibold text-ink">Votre recherche sera expliquée ici</h2>
            <p className="mx-auto mt-1 max-w-lg text-sm leading-6 text-slate-600">Chaque résultat présente ses sources, les versions contradictoires et les éléments qui manquent pour conclure.</p>
          </section>
        ) : null}
      </main>
    </div>
  );
}

/** Application enveloppée par une frontière d'erreur globale. */
export default function App() {
  return <ErrorBoundary><TrustLensApp /></ErrorBoundary>;
}
