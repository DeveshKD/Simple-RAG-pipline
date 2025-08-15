'use client';
import { useAuthStore } from '@/store/authStore';
import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, verifyAuth } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    verifyAuth();
  }, [verifyAuth]);

  useEffect(() => {
    if (!isLoading) {
      const isAuthPage = pathname === '/login' || pathname === '/register';
      
      if (!isAuthenticated && !isAuthPage) {
        router.push('/login');
      }
      
      if (isAuthenticated && isAuthPage) {
        router.push('/');
      }
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (pathname === '/login' || pathname === '/register') {
      return <>{children}</>;
  }

  if (isAuthenticated) {
      return <>{children}</>;
  }

  return null;
}