import { create } from 'zustand';
import { apiClient } from '@/lib/api';
import { DocumentInfo } from './documentStore';

export interface ChatMessage {
  id: string | null;
  role: string;
  content: string;
  timestamp: string | null;
}

export interface InteractionInfo {
  id: string;
  title: string;
  created_at: string;
}

export interface InteractionHistory {
  id: string;
  title: string;
  created_at: string;
  documents: DocumentInfo[];
  messages: ChatMessage[];
}

interface InteractionState {
  interactions: InteractionInfo[];
  currentInteraction: InteractionHistory | null;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
}

interface InteractionActions {
  fetchInteractions: () => Promise<void>;
  fetchInteractionHistory: (interactionId: string) => Promise<void>;
  createInteractionWithDocument: (file: File) => Promise<string | null>;
  addDocumentToInteraction: (interactionId: string, file: File) => Promise<boolean>;
  sendMessage: (interactionId: string, message: string) => Promise<boolean>;
  deleteInteraction: (interactionId: string) => Promise<boolean>;
  unlinkDocumentFromInteraction: (interactionId: string, documentId: string) => Promise<boolean>;
  setCurrentInteraction: (interaction: InteractionHistory | null) => void;
  clearError: () => void;
  addOptimisticMessage: (message: ChatMessage) => void;
  updateLastMessage: (content: string) => void;
}

type InteractionStore = InteractionState & InteractionActions;

export const useInteractionStore = create<InteractionStore>((set, get) => ({
  // State
  interactions: [],
  currentInteraction: null,
  isLoading: false,
  isSending: false,
  error: null,

  // Actions
  fetchInteractions: async (): Promise<void> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.getInteractions();
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return;
      }

      set({ 
        interactions: response.data || [],
        isLoading: false,
        error: null 
      });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch interactions',
        isLoading: false 
      });
    }
  },

  fetchInteractionHistory: async (interactionId: string): Promise<void> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.getInteractionHistory(interactionId);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return;
      }

      set({ 
        currentInteraction: response.data || null,
        isLoading: false,
        error: null 
      });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch interaction history',
        isLoading: false 
      });
    }
  },

  createInteractionWithDocument: async (file: File): Promise<string | null> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.createInteractionWithDocument(file);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return null;
      }

      const interactionState = response.data?.interaction_state;
      
      if (interactionState) {
        set({ 
          currentInteraction: interactionState,
          isLoading: false,
          error: null 
        });
        
        // Refresh interactions list
        get().fetchInteractions();
        
        return interactionState.id;
      }
      
      return null;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to create interaction',
        isLoading: false 
      });
      return null;
    }
  },

  addDocumentToInteraction: async (interactionId: string, file: File): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.addDocumentToInteraction(interactionId, file);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      const interactionState = response.data?.interaction_state;
      
      if (interactionState) {
        set({ 
          currentInteraction: interactionState,
          isLoading: false,
          error: null 
        });
      }
      
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to add document to interaction',
        isLoading: false 
      });
      return false;
    }
  },

  sendMessage: async (interactionId: string, message: string): Promise<boolean> => {
    set({ isSending: true, error: null });
    
    // Add optimistic user message
    get().addOptimisticMessage({
      id: null,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    });
    
    try {
      const response = await apiClient.sendMessageToInteraction(interactionId, message);
      
      if (response.error) {
        set({ error: response.error, isSending: false });
        return false;
      }

      // Add assistant response
      if (response.data?.synthesized_answer) {
        get().addOptimisticMessage({
          id: null,
          role: 'assistant',
          content: response.data.synthesized_answer,
          timestamp: new Date().toISOString(),
        });
      }
      
      set({ isSending: false, error: null });
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to send message',
        isSending: false 
      });
      return false;
    }
  },

  deleteInteraction: async (interactionId: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.deleteInteraction(interactionId);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      // Remove from local state
      set((state) => ({
        interactions: state.interactions.filter(interaction => interaction.id !== interactionId),
        currentInteraction: state.currentInteraction?.id === interactionId ? null : state.currentInteraction,
        isLoading: false,
        error: null
      }));
      
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to delete interaction',
        isLoading: false 
      });
      return false;
    }
  },

  unlinkDocumentFromInteraction: async (interactionId: string, documentId: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    
    try {
      const response = await apiClient.unlinkDocumentFromInteraction(interactionId, documentId);
      
      if (response.error) {
        set({ error: response.error, isLoading: false });
        return false;
      }

      // Update current interaction if it's the active one
      const { currentInteraction } = get();
      if (currentInteraction && currentInteraction.id === interactionId) {
        set({
          currentInteraction: {
            ...currentInteraction,
            documents: currentInteraction.documents.filter(doc => doc.id !== documentId)
          },
          isLoading: false,
          error: null
        });
      }
      
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to unlink document',
        isLoading: false 
      });
      return false;
    }
  },

  setCurrentInteraction: (interaction: InteractionHistory | null) => {
    set({ currentInteraction: interaction });
  },

  clearError: () => set({ error: null }),

  addOptimisticMessage: (message: ChatMessage) => {
    set((state) => {
      if (!state.currentInteraction) return state;
      
      return {
        currentInteraction: {
          ...state.currentInteraction,
          messages: [...state.currentInteraction.messages, message]
        }
      };
    });
  },

  updateLastMessage: (content: string) => {
    set((state) => {
      if (!state.currentInteraction || state.currentInteraction.messages.length === 0) {
        return state;
      }
      
      const messages = [...state.currentInteraction.messages];
      const lastMessage = messages[messages.length - 1];
      
      if (lastMessage.role === 'assistant') {
        messages[messages.length - 1] = { ...lastMessage, content };
      }
      
      return {
        currentInteraction: {
          ...state.currentInteraction,
          messages
        }
      };
    });
  },
}));