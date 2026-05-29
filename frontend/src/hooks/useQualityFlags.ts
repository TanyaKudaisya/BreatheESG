/**
 * React Query hooks for data quality flag operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  qualityFlagsService,
  type QualityFlagFilters,
} from '../services/qualityFlagsService';
import { emissionKeys } from './useEmissions';

export const flagKeys = {
  all: ['quality-flags'] as const,
  lists: () => [...flagKeys.all, 'list'] as const,
  list: (filters: QualityFlagFilters) => [...flagKeys.lists(), filters] as const,
};

export function useQualityFlags(filters: QualityFlagFilters = {}) {
  return useQuery({
    queryKey: flagKeys.list(filters),
    queryFn: () => qualityFlagsService.list(filters),
  });
}

export function useResolveFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => qualityFlagsService.resolve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: flagKeys.all });
      // Also refresh emissions since flag counts change
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}
