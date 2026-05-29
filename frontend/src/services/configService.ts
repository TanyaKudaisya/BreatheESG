/**
 * Service functions for the /api/v1/config/ endpoints.
 */

import apiClient from './apiClient';
import type { EmissionFactors, UnitConversions } from '../types';

export const configService = {
  /** Retrieve the currently loaded emission factors. */
  getEmissionFactors: async (): Promise<EmissionFactors> => {
    const { data } = await apiClient.get<EmissionFactors>(
      '/config/emission-factors/',
    );
    return data;
  },

  /** Retrieve the currently loaded unit conversion rates. */
  getUnitConversions: async (): Promise<UnitConversions> => {
    const { data } = await apiClient.get<UnitConversions>(
      '/config/unit-conversions/',
    );
    return data;
  },
};
