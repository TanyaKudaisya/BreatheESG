/**
 * Service functions for the /api/v1/ingest/ endpoints.
 */

import apiClient from './apiClient';
import type { IngestionResult } from '../types';

export const ingestionService = {
  /**
   * Upload a SAP tab-separated file.
   * @param file - The .txt file selected by the user
   */
  uploadSAP: async (file: File): Promise<IngestionResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await apiClient.post<IngestionResult>(
      '/ingest/sap/',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return data;
  },

  /**
   * Upload a utility electricity CSV file.
   * @param file - The .csv file selected by the user
   */
  uploadUtility: async (file: File): Promise<IngestionResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await apiClient.post<IngestionResult>(
      '/ingest/utility/',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return data;
  },

  /**
   * Post a Concur JSON travel expense payload.
   * @param payload - Parsed JSON object matching Concur Expense v3 schema
   */
  postTravel: async (payload: unknown): Promise<IngestionResult> => {
    const { data } = await apiClient.post<IngestionResult>(
      '/ingest/travel/',
      payload,
    );
    return data;
  },
};
