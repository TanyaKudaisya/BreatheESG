/**
 * React Query hooks for authentication.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';
import type { LoginPayload } from '../types';

export const authKeys = {
  me: ['auth', 'me'] as const,
};

export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginPayload) => authService.login(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(authKeys.me, data.user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async () => {
      console.log('useLogout: Starting logout mutation');
      await authService.logout();
      console.log('useLogout: Logout service call completed');
    },
    onSuccess: () => {
      console.log('useLogout: onSuccess called, clearing cache and navigating');
      queryClient.clear();
      navigate('/login', { replace: true });
    },
    onError: (error) => {
      console.error('useLogout: Logout failed:', error);
      // Even if the API call fails, clear local state and redirect
      queryClient.clear();
      localStorage.removeItem('auth_token');
      navigate('/login', { replace: true });
    },
  });
}
