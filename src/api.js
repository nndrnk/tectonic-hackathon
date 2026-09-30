import conflictMock from "./mock_response.json";
import confidentMock from "./mock_confident.json";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const VALID_COUNTRIES = new Set(["BE", "FR", "NL"]);
const VALID_SUBJECTS = new Set(["worker", "group"]);
const WEIGHT_NAMES = ["freshness", "authority", "owner", "country"];

let accessToken = null;
let expiresAt = 0;

/** Nettoie les caractères de contrôle sans transformer le texte affiché. */
function cleanText(value) {
  return String(value ?? "").replace(/[\u0000-\u001f\u007f]/g, "");
}

/** Retourne une copie indépendante d'un mock pour éviter de muter le module. */
function cloneMock(mock) {
  return JSON.parse(JSON.stringify(mock));
}

/** Notifie l'application que la session doit être abandonnée. */
function expireSession() {
  accessToken = null;
  expiresAt = 0;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("trustlens:session-expired"));
  }
}

/** Vérifie la session en mémoire et retourne son jeton pour l'appel courant. */
function requireToken() {
  if (!accessToken || Date.now() >= expiresAt) {
    expireSession();
    throw new Error("Session expirée. Reconnectez-vous.");
  }
  return accessToken;
}

/** Valide les champs de connexion selon les limites du contrat API. */
function validateCredentials(credentials) {
  const username = cleanText(credentials?.username).trim();
  const password = cleanText(credentials?.password);
  if (username.length < 3 || username.length > 32 || password.length < 8 || password.length > 128) {
    throw new Error("Identifiant ou mot de passe invalide.");
  }
  return { username, password };
}

/** Valide et normalise une recherche avant de la transmettre au backend. */
function validateSearch(payload) {
  const query = cleanText(payload?.query).trim();
  const country = payload?.country;
  const subject = payload?.subject;
  if (query.length < 3 || query.length > 300) {
    throw new Error("La question doit contenir entre 3 et 300 caractères.");
  }
  if (!VALID_COUNTRIES.has(country) || !VALID_SUBJECTS.has(subject)) {
    throw new Error("Paramètres de recherche invalides.");
  }
  let weights;
  if (payload?.weights != null) {
    weights = {};
    for (const name of WEIGHT_NAMES) {
      const value = Number(payload.weights[name]);
      if (!Number.isFinite(value) || value < 0 || value > 1) {
        throw new Error("Les poids doivent être compris entre 0 et 1.");
      }
      weights[name] = value;
    }
  }
  return { query, country, subject, ...(weights ? { weights } : {}) };
}

/** Vérifie et normalise une demande d'analyse de texte collé. */
function validateAnalyze(payload) {
  const text = cleanText(payload?.text).trim();
  const country = payload?.country;
  if (text.length < 20 || text.length > 5000 || !VALID_COUNTRIES.has(country)) {
    throw new Error("Le texte doit contenir entre 20 et 5 000 caractères et un pays valide.");
  }
  return { text, country };
}

/** Effectue une requête authentifiée sans révéler le corps d'erreur du serveur. */
async function request(path, body, signal) {
  const token = requireToken();
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new Error("Connexion impossible. Vérifiez le serveur et réessayez.");
  }

  if (response.status === 401) {
    expireSession();
    throw new Error("Session expirée. Reconnectez-vous.");
  }
  if (!response.ok) {
    throw new Error("La demande n’a pas abouti. Réessayez.");
  }
  try {
    return await response.json();
  } catch {
    throw new Error("La réponse du serveur est indisponible. Réessayez.");
  }
}

/**
 * Connecte un utilisateur. En mode mock, tout couple conforme aux longueurs est accepté.
 * Le jeton reste uniquement dans la mémoire du module.
 * @param {{username: string, password: string}} credentials
 * @returns {Promise<{role: string, expires_in: number}>}
 */
export async function login(credentials) {
  const safeCredentials = validateCredentials(credentials);
  let session;
  if (USE_MOCK) {
    session = { access_token: "mock-session-token", role: "employee", expires_in: 1800 };
  } else {
    let response;
    try {
      response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(safeCredentials),
      });
    } catch (error) {
      if (error?.name === "AbortError") throw error;
      throw new Error("Connexion impossible. Vérifiez le serveur et réessayez.");
    }
    if (!response.ok) throw new Error("Connexion impossible. Vérifiez vos identifiants.");
    try {
      session = await response.json();
    } catch {
      throw new Error("La réponse du serveur est indisponible. Réessayez.");
    }
  }

  if (
    typeof session?.access_token !== "string" ||
    !Number.isFinite(session?.expires_in) ||
    session.expires_in <= 0
  ) {
    throw new Error("La session reçue est invalide. Réessayez.");
  }
  accessToken = session.access_token;
  expiresAt = Date.now() + session.expires_in * 1000;
  return { role: session.role, expires_in: session.expires_in };
}

/**
 * Lance une recherche et retourne un SearchResult.
 * @param {{query: string, country: string, subject: string, weights?: object}} payload
 * @param {{signal?: AbortSignal}} [options]
 */
export async function search(payload, options = {}) {
  const safePayload = validateSearch(payload);
  requireToken();
  if (USE_MOCK) {
    const query = safePayload.query.toLocaleLowerCase("fr");
    return cloneMock(query.includes("transport") || query.includes("mobilité") ? confidentMock : conflictMock);
  }
  return request("/search", safePayload, options.signal);
}

/**
 * Analyse du texte fourni par l'utilisateur.
 * @param {{text: string, country: string}} payload
 * @param {{signal?: AbortSignal}} [options]
 */
export async function analyzeText(payload, options = {}) {
  const safePayload = validateAnalyze(payload);
  requireToken();
  if (USE_MOCK) return cloneMock(conflictMock);
  return request("/analyze-text", safePayload, options.signal);
}

/** Enregistre un retour de document sans modifier le score côté navigateur. */
export async function sendFeedback(docId, vote) {
  const safeId = cleanText(docId).trim();
  if (!safeId || safeId.length > 20 || !["useful", "wrong"].includes(vote)) {
    throw new Error("Votre retour ne peut pas être envoyé.");
  }
  requireToken();
  if (USE_MOCK) return { ok: true };
  return request("/feedback", { doc_id: safeId, vote });
}

/** Déconnecte l'utilisateur et efface le jeton de la mémoire du module. */
export function logout() {
  expireSession();
}

/** Retourne le nombre de secondes de session encore disponibles. */
export function getSessionSeconds() {
  if (!accessToken) return 0;
  const remaining = Math.ceil((expiresAt - Date.now()) / 1000);
  if (remaining <= 0) {
    expireSession();
    return 0;
  }
  return remaining;
}
