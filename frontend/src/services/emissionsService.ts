/**
 * Service functions for the /api/v1/emissions/ endpoints.
 */

import apiClient from './apiClient';
import type {
  EmissionRecord,
  PaginatedResponse,
  EmissionRecordFilters,
  EditEmissionRecordPayload,
  ApproveRecordPayload,
  RejectRecordPayload,
  ScopeOverridePayload,
} from '../types';

export const emissionsService = {
  /** List emission records with optional filters and pagination. */
  list: async (
    filters: EmissionRecordFilters = {},
  ): Promise<PaginatedResponse<EmissionRecord>> => {
    const { data } = await apiClient.get<PaginatedResponse<EmissionRecord>>(
      '/emissions/',
      { params: filters },
    );
    return data;
  },

  /** Retrieve a single emission record by ID. */
  get: async (id: string): Promise<EmissionRecord> => {
    const { data } = await apiClient.get<EmissionRecord>(`/emissions/${id}/`);
    return data;
  },

  /** Partially update an emission record (quantity, unit, date, location). */
  update: async (
    id: string,
    payload: EditEmissionRecordPayload,
  ): Promise<EmissionRecord> => {
    const { data } = await apiClient.patch<EmissionRecord>(
      `/emissions/${id}/`,
      payload,
    );
    return data;
  },

  /** Approve a single emission record. */
  approve: async (id: string): Promise<EmissionRecord> => {
    const { data } = await apiClient.post<EmissionRecord>(
      `/emissions/${id}/approve/`,
    );
    return data;
  },

  /** Reject a single emission record with a reason. */
  reject: async (id: string, reason: string): Promise<EmissionRecord> => {
    const { data } = await apiClient.post<EmissionRecord>(
      `/emissions/${id}/reject/`,
      { reason },
    );
    return data;
  },

  /** Bulk approve multiple emission records. */
  bulkApprove: async (payload: ApproveRecordPayload): Promise<{ approved: number }> => {
    const { data } = await apiClient.post<{ approved: number }>(
      '/emissions/bulk-approve/',
      payload,
    );
    return data;
  },

  /** Bulk reject multiple emission records. */
  bulkReject: async (payload: RejectRecordPayload): Promise<{ rejected: number }> => {
    const { data } = await apiClient.post<{ rejected: number }>(
      '/emissions/bulk-reject/',
      payload,
    );
    return data;
  },

  /** Lock an emission record for audit. */
  lock: async (id: string): Promise<EmissionRecord> => {
    const { data } = await apiClient.post<EmissionRecord>(
      `/emissions/${id}/lock/`,
    );
    return data;
  },

  /** Unlock an emission record (auditor role required). */
  unlock: async (id: string): Promise<EmissionRecord> => {
    const { data } = await apiClient.post<EmissionRecord>(
      `/emissions/${id}/unlock/`,
    );
    return data;
  },

  /** Override scope classification with a justification note. */
  overrideScope: async (
    id: string,
    payload: ScopeOverridePayload,
  ): Promise<EmissionRecord> => {
    const { data } = await apiClient.post<EmissionRecord>(
      `/emissions/${id}/override-scope/`,
      payload,
    );
    return data;
  },
};
