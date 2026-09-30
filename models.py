from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["official_policy", "procedure", "email", "teams_chat", "expert_note"]
Country = Literal["BE", "FR", "NL", "ALL"]
SearchCountry = Literal["BE", "FR", "NL"]
Role = Literal["employee", "hr", "payroll_expert"]
Status = Literal["confident", "conflict", "low"]

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Document(Strict):
    id: str
    title: str
    content: str
    source_type: SourceType
    owner: Optional[str]
    country: Country
    last_updated: str            # ISO 8601
    copy_of: Optional[str]
    claim: str
    claim_quote: str             # phrase exacte présente dans content
    normalized_value: str        # ex: "preavis_3_mois"
    access_level: Role           # rôle minimum requis (employee < hr < payroll_expert)
    expert_validated: bool
    review_due: Optional[str]    # date ISO de prochaine révision (pour signaler l'expiration)

class Expert(Strict):
    name: str
    team: str
    country: Country
    topics: list[str]

class Claim(Strict):
    doc_id: str
    claim_text: str
    normalized_value: str
    quote: str
    needs_review: bool = False
    suspicious: bool = False     # injection de prompt détectée

class Weights(Strict):
    freshness: float = Field(0.30, ge=0, le=1)
    authority: float = Field(0.25, ge=0, le=1)
    owner: float = Field(0.20, ge=0, le=1)
    country: float = Field(0.25, ge=0, le=1)

class Breakdown(Strict):
    freshness: float
    authority: float
    owner: float
    country: float

class SourceOut(Strict):
    doc_id: str
    title: str
    score: float                 # 0 à 1
    breakdown: Breakdown
    is_duplicate: bool
    quote: str
    needs_review: bool
    suspicious: bool
    expiring_soon: bool = False

class Branch(Strict):
    value: str                   # normalized_value
    claim_text: str
    score: float                 # 0 à 1
    share: float                 # part normalisée 0 à 100
    sources: list[SourceOut]

class Stats(Strict):
    reliable_docs_pct: float
    total_docs: int
    reliable_docs: int           # score > 0.6
    duplicates_collapsed: int

class SuggestedExpert(Strict):
    name: str
    team: str

class SearchResult(Strict):
    status: Status
    answer: Optional[str]        # null si conflict ou low
    confidence: float            # 0 à 100
    branches: list[Branch]       # TOUTES les branches, jamais de conflit caché
    stats: Stats
    warnings: list[str]          # en français
    suggested_expert: Optional[SuggestedExpert]

class SearchRequest(Strict):
    query: str = Field(min_length=3, max_length=300)
    country: SearchCountry
    subject: Literal["worker", "group"]   # cas concerné : un travailleur ou un groupe
    weights: Optional[Weights] = None

class LoginRequest(Strict):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

class TokenResponse(Strict):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int              # secondes (1800)
    role: Role

class AnalyzeTextRequest(Strict):
    text: str = Field(min_length=20, max_length=5000)
    country: SearchCountry

class FeedbackRequest(Strict):
    doc_id: str = Field(min_length=1, max_length=20)
    vote: Literal["useful", "wrong"]
