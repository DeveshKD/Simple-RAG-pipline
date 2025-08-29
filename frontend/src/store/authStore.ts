import { create } from 'zustand';
import { apiClient } from '@/lib/api';

export interface User {
  id: string;
  email: string;
  is_active: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
}

interface AuthActions {
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

type AuthStore = AuthState & AuthActions;

export const useAuthStore = create<AuthStore>((set, get) => ({
  // State
  user: null,
  token: null,
  isLoading: false,
  error: null,
  isAuthenticated: false,

  // Actions
  login: async (email: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.login(email, password);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      if (response.data) {
        const { access_token } = response.data;
        
        // Set token in API client
        apiClient.setToken(access_token);
        
        // Get user info
        const userResponse = await apiClient.getCurrentUser();
        
        if (userResponse.error) {
          set({ error: userResponse.error, isLoading: false });
          return false;
        }

        set({
          token: access_token,
          user: userResponse.data || null,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
        
        return true;
      }
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Login failed', 
        isLoading: false 
      });
    }
    
    return false;
  },

  register: async (email: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.register(email, password);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      set({ isLoading: false, error: null });
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Registration failed', 
        isLoading: false 
      });
      return false;
    }
  },

  logout: async (): Promise<void> => {
    set({ isLoading: true });
    
    try {
      await apiClient.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear everything regardless of logout response
      apiClient.setToken(null);
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  checkAuth: async (): Promise<void> => {
    const token = apiClient.getToken();
    
    if (!token) {
      set({ isAuthenticated: false });
      return;
    }

    set({ isLoading: true });
    
    try {
      const response = await apiClient.getCurrentUser();
      
      if (response.error) {
        // Token is invalid, clear it
        apiClient.setToken(null);
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
        });
        return;
      }

      set({
        user: response.data || null,
        token,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      apiClient.setToken(null);
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },

  clearError: () => set({ error: null }),
  
  setLoading: (loading: boolean) => set({ isLoading: loading }),
}));