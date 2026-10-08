/**
 * Diagnostic feature API client (AGENTS.md 3.6.2).
 *
 * Wraps the Phase 3 quiz/profile endpoints; components never call fetch
 * directly. Types mirror backend schemas/quiz.py.
 */

import { apiClient } from '../../lib/apiClient';
import type {
  AssessmentRequest,
  AssessmentResult,
  ProfileResponse,
  QuizResponse,
} from '../../types/api';

/** Fetch the servable quiz questions (answers never included by the backend). */
export function getQuiz(): Promise<QuizResponse> {
  return apiClient.get<QuizResponse>('/quiz');
}

/**
 * Create (or idempotently fetch) the anonymous profile for a client UUID.
 */
export function createProfile(profileId: string): Promise<ProfileResponse> {
  return apiClient.post<ProfileResponse>('/profiles', { profile_id: profileId });
}

/**
 * Submit interests + answers; the backend scores server-side and returns
 * readiness, per-question feedback and weak concepts.
 */
export function submitAssessment(
  profileId: string,
  payload: AssessmentRequest,
): Promise<AssessmentResult> {
  return apiClient.post<AssessmentResult>(
    `/profiles/${encodeURIComponent(profileId)}/assessment`,
    payload,
  );
}

/** Fetch the profile's most recent scored assessment (404 if none yet). */
export function getLatestAssessment(profileId: string): Promise<AssessmentResult> {
  return apiClient.get<AssessmentResult>(
    `/profiles/${encodeURIComponent(profileId)}/assessments/latest`,
  );
}
