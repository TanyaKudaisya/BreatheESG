/**
 * React Query hook for audit trail retrieval.
 */

import { useQuery } from '@tanstack/react-query';
import { auditService } from '../services/auditService';

export const auditKeys = {
  trail: (recordId: string) => ['audit-trail', recordId] as const,
};

export function useAuditTrail(recordId: string) {
  return useQuery({
    queryKey: auditKeys.trail(recordId),
    queryFn: () => auditService.getTrail(recordId),
    enabled: Boolean(recordId),
  });
}
