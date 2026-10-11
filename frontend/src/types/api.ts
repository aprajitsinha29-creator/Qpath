/**
 * TypeScript mirror of backend API schemas (AGENTS.md 3.6.1).
 *
 * All request/response contracts between FastAPI (/api/v1) and the React
 * client are declared here. Phase 1 adds the pulse feature types; each field
 * mirrors a backend Pydantic schema (app/schemas/*.py).
 */

export interface HealthResponse {
  status: 'ok' | 'error';
  version: string;
  env: string;
  db: 'ok' | 'error';
}

export interface ApiErrorDetail {
  code: string;
  message: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

// ------------------------------------------------------------------ taxonomy

export interface SubfieldOut {
  id: string;
  name: string;
  description: string;
  sort_order: number;
  is_scored: boolean;
}

export interface ConceptOut {
  id: string;
  subfield_id: string;
  name: string;
  description: string;
  prerequisites: string[];
}

export interface CareerPathOut {
  id: string;
  title: string;
  subfield_id: string;
  description: string;
  typical_titles: string[];
}

export interface TaxonomyResponse {
  subfields: SubfieldOut[];
  concepts: ConceptOut[];
  career_paths: CareerPathOut[];
}

// --------------------------------------------------------------------- pulse

/** One skill share entry (backend schemas.pulse.SkillShare). */
export interface SkillShare {
  skill_id: string;
  name: string;
  /** Fraction 0–1 of extracted postings mentioning this skill. */
  share: number;
}

/** One paper reference inside a theme (backend schemas.pulse.PaperRef). */
export interface PaperRef {
  id: number;
  title: string;
  link: string | null;
}

/** One research theme with supporting paper links (backend schemas.pulse.ThemeOut). */
export interface ThemeOut {
  label: string;
  summary: string;
  papers: PaperRef[];
}

/** One Market Pulse card (backend schemas.pulse.PulseCard).
 * Phase 2 adds top_skills and themes as optional additive fields. */
export interface PulseCard {
  subfield_id: string;
  name: string;
  description: string;
  active_postings: number;
  extra_postings: number;
  internship_postings: number;
  /** Null until tracking spans >= 2 ingestion days (backend rule). */
  new_this_week: number | null;
  /** ISO date (yyyy-mm-dd) of the earliest first-seen posting, or null. */
  tracking_since: string | null;
  top_companies: string[];
  low_data: boolean;
  /** Phase 2: top 5 skills extracted from postings. Empty until extraction runs. */
  top_skills: SkillShare[];
  /** Phase 2: top 3 research themes from Scholar. Empty until scholar refresh runs. */
  themes: ThemeOut[];
}

/**
 * Full subfield detail (backend schemas.pulse.SubfieldDetail).
 * Returned by GET /pulse/{subfield_id}.
 */
export interface SubfieldDetail extends PulseCard {
  /** Full skill list (not capped at 5). */
  top_skills: SkillShare[];
  /** Per-seniority post counts (keys: intern/entry/mid/senior/lead/postdoc/phd_student/faculty/unknown). */
  seniority_mix: Record<string, number>;
  /** Fraction 0–1 of postings with requires_phd=true among those that stated it; null if unknown. */
  phd_share: number | null;
  /** Fraction 0–1 of all postings that have been extracted. */
  extraction_coverage: number;
  /** All research themes with full paper lists. */
  themes: ThemeOut[];
  /** Paginated list of job postings. */
  postings: PostingOut[];
}

/** One posting in a list view (backend schemas.pulse.PostingOut). */
export interface PostingOut {
  id: number;
  title: string;
  company: string;
  location: string | null;
  via: string | null;
  apply_url: string | null;
  is_internship: boolean;
  first_seen_at: string;
  snippet: string | null;
}

export interface PostingListResponse {
  total: number;
  limit: number;
  offset: number;
  items: PostingOut[];
}

export type PulseRegion = 'global' | 'india';

// ---------------------------------------------------------------------- meta

export interface SerpApiCallOut {
  id: number;
  engine: string;
  query: string;
  source: string;
  status: string;
  created_at: string;
}

export interface SerpApiActivity {
  mode: 'fixtures' | 'live';
  live_calls_today: number;
  daily_cap: number;
  recent_calls: SerpApiCallOut[];
}

// --------------------------------------------------------------------- admin

export type RefreshMode = 'bootstrap' | 'daily';

export interface RefreshJobsRequest {
  mode: RefreshMode;
  region: PulseRegion;
  subfield_id?: string | null;
}

export interface RefreshSummary {
  run_id: number;
  kind: string;
  mode: string;
  region: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  serpapi_calls: number;
  postings_seen: number;
  postings_new: number;
  postings_deactivated: number;
  queries_run: number;
  errors: string[];
}

// ----------------------------------------------------------------- quiz (Phase 3)

/** One servable quiz question. The backend NEVER sends answers (AGENTS.md 3.10.3). */
export interface QuizQuestion {
  id: string;
  subfield_id: string;
  concept_id: string;
  difficulty: number;
  stem: string;
  options: string[];
}

export interface QuizResponse {
  questions: QuizQuestion[];
}

/** One submitted answer; selected_index null = "Not sure". */
export interface AnswerIn {
  question_id: string;
  selected_index: number | null;
}

export interface AssessmentRequest {
  interests: Record<string, number>;
  answers: AnswerIn[];
}

/** Per-question result, returned only after scoring (never by GET /quiz). */
export interface PerQuestionFeedback {
  question_id: string;
  correct: boolean;
  explanation: string;
  concept_id: string;
}

export interface AssessmentResult {
  assessment_id: number;
  profile_id: string;
  taken_at: string;
  /** {subfield_id: readiness 0-100} */
  scores: Record<string, number>;
  interests: Record<string, number>;
  per_question: PerQuestionFeedback[];
  weak_concepts: string[];
}

export interface ProfileResponse {
  profile_id: string;
  created_at: string;
  interests: Record<string, number>;
  /** Vocabulary-validated skill ids declared via PUT /profiles/{id}/skills (additive). */
  declared_skills: string[];
  /** The tracked career path (set via PUT /profiles/{id}/chosen-path, Phase 5). */
  chosen_path_id: string | null;
}

// --------------------------------------------------------------------- skills (carry-over from Phase 4)

/** One vocabulary entry returned by GET /skills. */
export interface SkillOut {
  id: string;
  name: string;
  aliases: string[];
  subfield_ids: string[];
}

/** GET /skills returns a bare SkillOut[] sorted by name (mirror of app/schemas/skills.py). */
export type SkillsListResponse = SkillOut[];

/** PUT /profiles/{id}/skills request body: the complete replacement list. */
export interface DeclaredSkillsRequest {
  skill_ids: string[];
}

// ------------------------------------------------------------------- paths (Phase 4)

/** Skill share entry in a path's evidence panel. */
export interface PathSkillShare {
  skill_id: string;
  name: string;
  /** Fraction 0–1 of extracted postings mentioning this skill. */
  share: number;
  /** Percent rendering of share (1 decimal) — what explanations may cite. */
  share_pct: number;
}

/** Live Pulse evidence assembled for one career path. */
export interface PathEvidence {
  active_postings: number;
  internship_postings: number;
  top_skills: PathSkillShare[];
  /** Fraction 0–1 of postings requiring a PhD; null when unknown. */
  phd_share: number | null;
  /** Percent rendering of phd_share, or null. */
  phd_share_pct: number | null;
  sample_postings: PostingOut[];
}

/** Transparent score breakdown; weights are the same 40/30/30 as percentages. */
export interface ScoreBreakdown {
  interest: number;
  demand: number;
  readiness: number;
  weights: Record<string, number>;
}

/** Grounded Gemini explanation for one path. */
export interface PathExplanationOut {
  headline: string;
  reasons: string[];
  caveat: string;
  next_step: string;
  generated_by: 'llm' | 'template';
  model: string | null;
  generated_at: string | null;
}

/** One ranked career path with score breakdown, evidence, and optional explanation. */
export interface PathResult {
  path_id: string;
  title: string;
  subfield_id: string;
  rank: number;
  score: number;
  breakdown: ScoreBreakdown;
  is_top3: boolean;
  /** active_postings < 8 → demand evidence is thin. */
  low_data: boolean;
  /** The subfield's core query hit the page cap in the latest bootstrap. */
  saturated: boolean;
  evidence: PathEvidence;
  /** Null until an explanation has been generated for this path. */
  explanation: PathExplanationOut | null;
}

/** GET /profiles/{id}/paths response. */
export interface PathsOut {
  profile_id: string;
  assessment_id: number;
  region: string;
  saturation_note: string | null;
  paths: PathResult[];
}

// --------------------------------------------------------- tracker (Phase 5)

/** PUT /profiles/{id}/chosen-path request/response (plan 5.1). */
export interface ChosenPathRequest {
  path_id: string;
}

export interface ChosenPathResponse {
  profile_id: string;
  chosen_path_id: string | null;
}

/** POST /profiles/{id}/seen response. */
export interface SeenResponse {
  profile_id: string;
  last_seen_at: string | null;
}

/** One matched posting in the opportunities feed (plan 5.3 item shape). */
export interface OpportunityItem {
  posting_id: number;
  title: string;
  company: string;
  location: string | null;
  via: string | null;
  apply_url: string | null;
  is_internship: boolean;
  first_seen_at: string;
  is_new: boolean;
  /** Match 0-100, or null = "not enough information". */
  match: number | null;
  matched_skills: string[];
}

/** GET /profiles/{id}/opportunities response. */
export interface OpportunitiesResponse {
  profile_id: string;
  path_id: string;
  region: string;
  first_visit: boolean;
  total: number;
  last_seen_at: string | null;
  last_refreshed_at: string | null;
  items: OpportunityItem[];
}

/** One day of a subfield's trend series (plan 5.4). */
export interface TrendPoint {
  date: string;
  active: number;
  new: number;
  internships: number;
}

/** Latest run per refresh kind, for the LastRefreshedPill (plan 5.4). */
export interface RefreshStatusEntry {
  time: string | null;
  status: string | null;
  serpapi_calls: number | null;
  counts: Record<string, number>;
  error: string | null;
}

export interface RefreshStatusResponse {
  jobs: RefreshStatusEntry | null;
  scholar: RefreshStatusEntry | null;
  extraction: RefreshStatusEntry | null;
}

/** Per-engine SerpApi call split (backend schemas.meta.EngineCallCounts). */
export interface EngineCallCounts {
  live: number;
  fixture: number;
}

/** GET /meta/method response: honest Method-page numbers (mirror of the Pydantic schema). */
export interface MethodStatsResponse {
  /** {engine: {live, fixture}} call totals over all time. */
  serpapi_calls: Record<string, EngineCallCounts>;
  postings_total: number;
  postings_active: number;
  extraction_done: number;
  themes_count: number;
  last_jobs_refresh: string | null;
  last_scholar_refresh: string | null;
}
