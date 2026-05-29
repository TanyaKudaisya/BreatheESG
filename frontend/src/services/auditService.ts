/**
 * Service functions for the /api/v1/audit-trail/ endpoints.
 */

import apiClient from './apiClient';
import type { AuditEvent } from '../types';

export const auditService = {
  /** Retrieve the complete audit trail for a single emission record. */
  getTrail: async (recordId: string): Promise<AuditEvent[]> => {
    const { data } = await apiClient.get<AuditEvent[]>(
      `/audit-trail/${recordId}/`,
    );
    return data;
  },
};
