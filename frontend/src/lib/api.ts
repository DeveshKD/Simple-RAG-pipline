const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  status: number;
}

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('auth_token');
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('auth_token', token);
      } else {
        localStorage.removeItem('auth_token');
      }
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      const isJson = response.headers.get('content-type')?.includes('application/json');
      const data = isJson ? await response.json() : await response.text();

      if (!response.ok) {
        return {
          error: data?.detail || data || 'An error occurred',
          status: response.status,
        };
      }

      return {
        data,
        status: response.status,
      };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : 'Network error',
        status: 0,
      };
    }
  }

  // Auth endpoints
  async login(email: string, password: string): Promise<ApiResponse<{ access_token: string; token_type: string }>> {
    const url = `${this.baseUrl}/api/v2/auth/jwt/login`;
    
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
      });

      const isJson = response.headers.get('content-type')?.includes('application/json');
      const data = isJson ? await response.json() : await response.text();

      if (!response.ok) {
        return {
          error: data?.detail || data || 'Login failed',
          status: response.status,
        };
      }

      return {
        data,
        status: response.status,
      };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : 'Network error',
        status: 0,
      };
    }
  }

  async register(email: string, password: string): Promise<ApiResponse<{ id: string; email: string; is_active: boolean }>> {
    return this.request('/api/v2/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async logout(): Promise<ApiResponse<any>> {
    return this.request('/api/v2/auth/jwt/logout', {
      method: 'POST',
    });
  }

  async getCurrentUser(): Promise<ApiResponse<{ id: string; email: string; is_active: boolean }>> {
    return this.request('/api/v2/users/me');
  }

  // Document endpoints
  async getDocuments(): Promise<ApiResponse<Array<{
    id: string;
    filename: string;
    source_type: string | null;
    created_at: string;
  }>>> {
    return this.request('/api/v2/documents');
  }

  async deleteDocument(documentId: string): Promise<ApiResponse<{ status: string; message: string }>> {
    return this.request(`/api/v2/document/${documentId}`, {
      method: 'DELETE',
    });
  }

  // Library endpoints
  async getLibraryDocuments(): Promise<ApiResponse<Array<{
    id: string;
    filename: string;
    source_type: string | null;
    created_at: string;
    linked_sessions: Array<{
      id: string;
      title: string;
      created_at: string;
    }>;
  }>>> {
    return this.request('/api/library/documents');
  }

  async uploadDocumentToLibrary(file: File): Promise<ApiResponse<{
    document: {
      id: string;
      filename: string;
      source_type: string | null;
      created_at: string;
    };
    message: string;
  }>> {
    const formData = new FormData();
    formData.append('file', file);

    return this.request('/api/library/document/upload', {
      method: 'POST',
      headers: {}, // Remove Content-Type for FormData
      body: formData,
    });
  }

  async deleteLibraryDocument(documentId: string): Promise<ApiResponse<{ status: string; message: string }>> {
    return this.request(`/api/library/document/${documentId}`, {
      method: 'DELETE',
    });
  }

  // Interaction endpoints
  async getInteractions(): Promise<ApiResponse<Array<{
    id: string;
    title: string;
    created_at: string;
  }>>> {
    return this.request('/api/v2/interactions');
  }

  async getInteractionHistory(interactionId: string): Promise<ApiResponse<{
    id: string;
    title: string;
    created_at: string;
    documents: Array<{
      id: string;
      filename: string;
      source_type: string | null;
      created_at: string;
    }>;
    messages: Array<{
      id: string | null;
      role: string;
      content: string;
      timestamp: string | null;
    }>;
  }>> {
    return this.request(`/api/v2/interaction/${interactionId}`);
  }

  async createInteractionWithDocument(file: File): Promise<ApiResponse<any>> {
    const formData = new FormData();
    formData.append('file', file);

    return this.request('/api/v2/interactions/with-document', {
      method: 'POST',
      headers: {},
      body: formData,
    });
  }

  async addDocumentToInteraction(interactionId: string, file: File): Promise<ApiResponse<any>> {
    const formData = new FormData();
    formData.append('interaction_id', interactionId);
    formData.append('file', file);

    return this.request('/api/v2/interactions/with-document', {
      method: 'POST',
      headers: {},
      body: formData,
    });
  }

  async sendMessageToInteraction(
    interactionId: string, 
    queryText: string
  ): Promise<ApiResponse<{
    interaction_id: string;
    synthesized_answer: string;
  }>> {
    return this.request(`/api/v2/interactions/${interactionId}/query`, {
      method: 'POST',
      body: JSON.stringify({ query_text: queryText }),
    });
  }

  async deleteInteraction(interactionId: string): Promise<ApiResponse<{ status: string; message: string }>> {
    return this.request(`/api/v2/interaction/${interactionId}`, {
      method: 'DELETE',
    });
  }

  async linkDocumentToInteraction(documentId: string, interactionId: string): Promise<ApiResponse<{ status: string; message: string }>> {
    return this.request(`/api/library/document/${documentId}/link-to/${interactionId}`, {
      method: 'POST',
    });
  }

  async unlinkDocumentFromInteraction(interactionId: string, documentId: string): Promise<ApiResponse<{ status: string; message: string }>> {
    return this.request(`/api/v2/interaction/${interactionId}/unlink-document/${documentId}`, {
      method: 'DELETE',
    });
  }

  async getAvailableInteractionsForDocument(documentId: string): Promise<ApiResponse<Array<{
    id: string;
    title: string;
    created_at: string;
  }>>> {
    return this.request(`/api/library/document/${documentId}/available-interactions`);
  }
}

export const apiClient = new ApiClient();