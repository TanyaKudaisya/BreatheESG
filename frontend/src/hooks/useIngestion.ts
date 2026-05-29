/**
 * React Query mutation hooks for file ingestion.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ingestionService } from '../services/ingestionService';
import { emissionKeys } from './useEmissions';

export function useIngestSAP() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => ingestionService.uploadSAP(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useIngestUtility() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => ingestionService.uploadUtility(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}

export function useIngestTravel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: unknown) => ingestionService.postTravel(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emissionKeys.all });
    },
  });
}
