import { create } from 'zustand';
import { apiClient } from '@/lib/api';

export interface DocumentInfo {
  id: string;
  filename: string;
  source_type: string | null;
  created_at: string;
}

export interface DocumentLibraryInfo extends DocumentInfo {
  linked_sessions: Array<{
    id: string;
    title: string;
    created_at: string;
  }>;
}

interface DocumentState {
  documents: DocumentInfo[];
  libraryDocuments: DocumentLibraryInfo[];
  isLoading: boolean;
  error: string | null;
  uploadProgress: number;
}

interface DocumentActions {
  fetchDocuments: () => Promise<void>;
  fetchLibraryDocuments: () => Promise<void>;
  uploadDocumentToLibrary: (file: File) => Promise<boolean>;
  deleteDocument: (documentId: string) => Promise<boolean>;
  deleteLibraryDocument: (documentId: string) => Promise<boolean>;
  linkDocumentToInteraction: (documentId: string, interactionId: string) => Promise<boolean>;
  clearError: () => void;
  setUploadProgress: (progress: number) => void;
}

type DocumentStore = DocumentState & DocumentActions;

export const useDocumentStore = create<DocumentStore>((set, get) => ({
  // State
  documents: [],
  libraryDocuments: [],
  isLoading: false,
  error: null,
  uploadProgress: 0,

  // Actions
  fetchDocuments: async (): Promise<void> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.getDocuments();
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return;
      }

      set({ 
        documents: response.data || [],
        isLoading: false,
        error: null 
      });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch documents',
        isLoading: false 
      });
    }
  },

  fetchLibraryDocuments: async (): Promise<void> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.getLibraryDocuments();
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return;
      }

      set({ 
        libraryDocuments: response.data || [],
        isLoading: false,
        error: null 
      });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch library documents',
        isLoading: false 
      });
    }
  },

  uploadDocumentToLibrary: async (file: File): Promise<boolean> => {
    set({ isLoading: true, error: null, uploadProgress: 0 });
    
    try {
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        set((state) => ({ 
          uploadProgress: Math.min(state.uploadProgress + 10, 90) 
        }));
      }, 200);

      const response = await apiClient.uploadDocumentToLibrary(file);
      
      clearInterval(progressInterval);
      set({ uploadProgress: 100 });

      if (response.error) {
        set({ error: response.error, isLoading: false, uploadProgress: 0 });
        return false;
      }

      // Refresh library documents
      await get().fetchLibraryDocuments();
      
      set({ isLoading: false, error: null, uploadProgress: 0 });
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to upload document',
        isLoading: false,
        uploadProgress: 0
      });
      return false;
    }
  },

  deleteDocument: async (documentId: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.deleteDocument(documentId);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      // Remove from local state
      set((state) => ({
        documents: state.documents.filter(doc => doc.id !== documentId),
        isLoading: false,
        error: null
      }));
      
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to delete document',
        isLoading: false 
      });
      return false;
    }
  },

  deleteLibraryDocument: async (documentId: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.deleteLibraryDocument(documentId);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      // Remove from local state
      set((state) => ({
        libraryDocuments: state.libraryDocuments.filter(doc => doc.id !== documentId),
        isLoading: false,
        error: null
      }));
      
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to delete library document',
        isLoading: false 
      });
      return false;
    }
  },

  linkDocumentToInteraction: async (documentId: string, interactionId: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.linkDocumentToInteraction(documentId, interactionId);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      // Refresh library documents to update linked sessions
      await get().fetchLibraryDocuments();
      
      set({ isLoading: false, error: null });
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to link document',
        isLoading: false 
      });
      return false;
    }
  },

  clearError: () => set({ error: null }),
  
  setUploadProgress: (progress: number) => set({ uploadProgress: progress }),
}));