/**
 * Service functions for authentication endpoints.
 */

import apiClient from './apiClient';
import type { LoginPayload, LoginResponse, User } from '../types';

export const authService = {
  /** Log in and store the returned token in localStorage. */
  login: async (payload: LoginPayload): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login/', payload);
    localStorage.setItem('auth_token', data.token);
    return data;
  },

  /** Log out and clear the stored token. */
  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout/');
    } catch (error) {
      // Log the error but don't throw - we want to clear local state regardless
      console.error('Logout API call failed:', error);
    } finally {
      // Always clear the token, even if the API call fails
      localStorage.removeItem('auth_token');
    }
  },

  /** Fetch the currently authenticated user's profile. */
  me: async (): Promise<User> => {
    const { data } = await apiClient.get<User>('/auth/me/');
    return data;
  },
};
