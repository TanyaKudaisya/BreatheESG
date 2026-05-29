/**
 * Service functions for the /api/v1/quality-flags/ endpoints.
 */

import apiClient from './apiClient';
import type { DataQualityFlag, PaginatedResponse, FlagType } from '../types';

export interface QualityFlagFilters {
  flag_type?: FlagType;
  is_resolved?: boolean;
  page?: number;
  page_size?: number;
}

export const qualityFlagsService = {
  /** List data quality flags with optional filters. */
  list: async (
    filters: QualityFlagFilters = {},
  ): Promise<PaginatedResponse<DataQualityFlag>> => {
    const { data } = await apiClient.get<PaginatedResponse<DataQualityFlag>>(
      '/quality-flags/',
      { params: filters },
    );
    return data;
  },

  /** Resolve a data quality flag. */
  resolve: async (id: string): Promise<DataQualityFlag> => {
    const { data } = await apiClient.post<DataQualityFlag>(
      `/quality-flags/${id}/resolve/`,
    );
    return data;
  },
};
