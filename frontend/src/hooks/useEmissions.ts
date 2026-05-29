/**
 * React Query hooks for emission record operations.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { emissionsService } from '../services/emissionsService';
import type {
  EmissionRecord,
  PaginatedResponse,
  EmissionRecordFilters,
  EditEmissionRecordPayload,
  ApproveRecordPayload,
  RejectRecordPayload,
  ScopeOverridePayload,
} from '../types';

// ─── Query keys ───────────────────────────────────────────────────────────────

export const emissionKeys = {
  all: ['emissions'] as const,
  lists: () => [...emissionKeys.all, 'list'] as const,
  list: (filters: EmissionRecordFilters) =>
    [...emissionKeys.lists(), filters] as const,
  details: () => [...emissionKeys.all, 'detail'] as const,
  detail: (id: string) => [...emissionKeys.details(), id] as const,
};

// ─── Queries ──────────────────────────────────────────────────────────────────

export function useEmissions(
  filters: EmissionRecordFilters = {},
  options?: Omit<
    UseQueryOptions<PaginatedResponse<EmissionRecord>>,
    'queryKey' | 'queryFn'
  >,
) {
  return useQuery({
    queryKey: emissionKeys.list(filters),
    queryFn: () => emissionsService.list(filters),
    ...options,
  });
}

export function useEmission(
  id: string,
  options?: Omit<
    UseQueryOptions<EmissionRecord>,
    'queryKey' | 'queryFn'
  >,
) {
  return useQuery({
    queryKey: emissionKeys.detail(id),
    queryFn: () => emissionsService.get(id),
    enabled: Boolean(id),
    ...options,
  });
}

// ─── Mutations ────────────────────────────────────────────────────────────────

export function useUpdateEmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: EditEmissionRecordPayload }) =>
      emissionsService.update(id, payload),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.lists() });
      queryClient.setQueryData(emissionKeys.detail(updated.id), updated);
    },
  });
}

export function useApproveEmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => emissionsService.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useRejectEmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      emissionsService.reject(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useBulkApprove() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ApproveRecordPayload) =>
      emissionsService.bulkApprove(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useBulkReject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RejectRecordPayload) =>
      emissionsService.bulkReject(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useLockEmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => emissionsService.lock(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useUnlockEmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => emissionsService.unlock(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useOverrideScope() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ScopeOverridePayload }) =>
      emissionsService.overrideScope(id, payload),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.lists() });
      queryClient.setQueryData(emissionKeys.detail(updated.id), updated);
    },
  });
}
