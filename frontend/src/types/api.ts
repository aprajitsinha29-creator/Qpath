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

/** One Market Pulse card (backend schemas.pulse.PulseCard). */
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
