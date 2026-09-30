/** @typedef {"BE" | "FR" | "NL"} SearchCountry */
/** @typedef {"worker" | "group"} Subject */
/** @typedef {"confident" | "conflict" | "low"} SearchStatus */
/** @typedef {"useful" | "wrong"} FeedbackVote */

/** Détail des quatre facteurs utilisés dans le calcul d'un document. */
/** @typedef {object} Breakdown
 * @property {number} freshness Valeur de fraîcheur entre 0 et 1.
 * @property {number} authority Valeur d'autorité entre 0 et 1.
 * @property {number} owner Valeur liée à la présence d'un propriétaire.
 * @property {number} country Valeur liée à l'adéquation géographique.
 */

/** Source individuelle attachée à une branche de résultat. */
/** @typedef {object} SourceOut
 * @property {string} doc_id Identifiant du document.
 * @property {string} title Titre non fiable à afficher comme texte.
 * @property {number} score Score du document entre 0 et 1.
 * @property {Breakdown} breakdown Détail des critères de scoring.
 * @property {boolean} is_duplicate Indique une copie déjà comptée dans le groupe.
 * @property {string} quote Citation exacte fournie par le backend.
 * @property {boolean} needs_review Indique une affirmation à vérifier.
 * @property {boolean} suspicious Indique un contenu signalé comme suspect.
 * @property {boolean} expiring_soon Indique une révision prévue dans les 60 jours.
 */

/** Branche correspondant à une valeur normalisée distincte. */
/** @typedef {object} Branch
 * @property {string} value Valeur normalisée qui identifie la branche.
 * @property {string} claim_text Affirmation présentée pour cette branche.
 * @property {number} score Score de branche entre 0 et 1.
 * @property {number} share Part de confiance normalisée entre 0 et 100.
 * @property {SourceOut[]} sources Sources qui soutiennent ou documentent la branche.
 */

/** Statistiques de fiabilité du jeu de documents analysé. */
/** @typedef {object} Stats
 * @property {number} reliable_docs_pct Pourcentage de documents dont le score dépasse 0.6.
 * @property {number} total_docs Nombre de documents fournis au scoring.
 * @property {number} reliable_docs Nombre de documents dont le score dépasse 0.6.
 * @property {number} duplicates_collapsed Nombre de copies exclues du calcul des branches.
 */

/** Personne suggérée pour examiner un résultat incertain. */
/** @typedef {object} SuggestedExpert
 * @property {string} name Nom d'affichage de l'expert.
 * @property {string} team Équipe ou domaine de l'expert.
 */

/** Réponse commune aux endpoints /search et /analyze-text. */
/** @typedef {object} SearchResult
 * @property {SearchStatus} status Statut global de la réponse.
 * @property {string | null} answer Réponse unique uniquement quand status vaut confident.
 * @property {number} confidence Confiance de la branche dominante, entre 0 et 100.
 * @property {Branch[]} branches Toutes les branches, contradictions incluses.
 * @property {Stats} stats Statistiques sur les documents.
 * @property {string[]} warnings Avertissements explicatifs en français.
 * @property {SuggestedExpert | null} suggested_expert Expert suggéré en cas d'incertitude.
 */

/** Poids personnalisés envoyés à l'API de recherche. */
/** @typedef {object} Weights
 * @property {number} freshness Poids de la fraîcheur entre 0 et 1.
 * @property {number} authority Poids de l'autorité entre 0 et 1.
 * @property {number} owner Poids du propriétaire entre 0 et 1.
 * @property {number} country Poids du pays entre 0 et 1.
 */

/** Corps de la requête de recherche. */
/** @typedef {object} SearchRequest
 * @property {string} query Question de 3 à 300 caractères.
 * @property {SearchCountry} country Pays demandé.
 * @property {Subject} subject Cas ciblé : travailleur ou groupe.
 * @property {Weights} [weights] Poids personnalisés facultatifs.
 */

/** Corps d'une requête d'analyse de texte collé. */
/** @typedef {object} AnalyzeTextRequest
 * @property {string} text Texte à analyser, de 20 à 5 000 caractères.
 * @property {SearchCountry} country Pays demandé.
 */

/** Corps du retour utilisateur sur un document. */
/** @typedef {object} FeedbackRequest
 * @property {string} doc_id Identifiant du document.
 * @property {FeedbackVote} vote Retour donné au document.
 */

/** Réponse de connexion ; le jeton ne doit rester qu'en mémoire. */
/** @typedef {object} LoginSession
 * @property {string} access_token Jeton bearer en mémoire.
 * @property {number} expires_in Durée de session en secondes.
 * @property {"employee" | "hr" | "payroll_expert"} role Rôle associé à la session.
 */

export {};
