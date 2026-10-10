/**
 * TanStack Query hooks for the skills feature (frontend rules 3.6.3).
 *
 * useSkills: fetches the vocabulary with a long staleTime — the seeded
 * vocabulary is effectively static, so refetching on every mount is waste.
 * useSaveDeclaredSkills: PUT mutation; on success the profile query cache is
 * updated so every consumer reads the fresh declared_skills instantly.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../../lib/apiClient';
import type { ProfileResponse } from '../../../types/api';
import { getSkills, putDeclaredSkills } from '../api';

const SKILLS_KEY = ['skills'] as const;
const PROFILE_KEY = (profileId: string) => ['profile', profileId] as const;

/** Fetch the skills vocabulary; stale one hour (seeded data is static). */
export function useSkills() {
  return useQuery({
    queryKey: SKILLS_KEY,
    queryFn: getSkills,
    staleTime: 60 * 60 * 1000,
  });
}

/**
 * Fetch the anonymous profile (source of pre-fill for declared_skills).
 * Defined here so the picker owns its whole data path; the query key is
 * exported for tests/consumers that need to prime the cache.
 */
export function useProfile(profileId: string) {
  return useQuery<ProfileResponse>({
    queryKey: PROFILE_KEY(profileId),
    queryFn: () => apiClient.get<ProfileResponse>(`/profiles/${encodeURIComponent(profileId)}`),
    staleTime: 5 * 60 * 1000,
  });
}

/** Hook key so tests and consumers use exactly the profile query key used here. */
export function profileQueryKey(profileId: string) {
  return PROFILE_KEY(profileId);
}

/**
 * Mutation replacing the profile's declared_skills. On success the profile
 * query cache is written with the returned profile, keeping every view of
 * `declared_skills` consistent without an extra fetch.
 */
export function useSaveDeclaredSkills(profileId: string) {
  const queryClient = useQueryClient();
  return useMutation<ProfileResponse, Error, string[]>({
    mutationFn: (skillIds) => putDeclaredSkills(profileId, skillIds),
    onSuccess: (profile) => {
      queryClient.setQueryData<ProfileResponse>(PROFILE_KEY(profileId), profile);
    },
  });
}
