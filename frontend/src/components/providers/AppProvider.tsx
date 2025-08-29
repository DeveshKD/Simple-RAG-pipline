'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';

interface AppProviderProps {
  children: React.ReactNode;
}

export default function AppProvider({ children }: AppProviderProps) {
  const { checkAuth } = useAuthStore();

  useEffect(() => {
    // Check authentication status on app initialization
    checkAuth();
  }, [checkAuth]);

  return <>{children}</>;
}