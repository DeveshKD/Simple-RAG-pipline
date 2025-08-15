import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { InteractionInfo, InteractionHistory } from '@/types/Interaction';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v2',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const { token } = useAuthStore.getState();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// auth related functions
export const registerUser = async (data: any) => {
  const response = await apiClient.post('/auth/register', data);
  return response.data;
};

export const loginUser = async (data: any) => {
  const formData = new URLSearchParams();
  formData.append('username', data.email);
  formData.append('password', data.password);

  const response = await apiClient.post('/auth/jwt/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
};

export const logoutUser = async () => {
  const response = await apiClient.post('/auth/jwt/logout');
  return response.data;
};

// other API functions
export const getAllInteractions = async (): Promise<InteractionInfo[]> => {
  const response = await apiClient.get('/interactions');
  return response.data;
};

export const getInteractionDetails = async (id: string): Promise<InteractionHistory> => {
  const response = await apiClient.get(`/interaction/${id}`);
  return response.data;
};

export const uploadDocument = async (file: File, interactionId: string | null): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  if (interactionId) {
    formData.append('interaction_id', interactionId);
  }
  const response = await apiClient.post('/interactions/with-document', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const postQuery = async (interactionId: string, queryText: string): Promise<any> => {
  const response = await apiClient.post(`/interactions/${interactionId}/query`, { query_text: queryText });
  return response.data;
};

export default apiClient;