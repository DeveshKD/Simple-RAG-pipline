import { create } from 'zustand';
import { InteractionInfo, ChatMessage, DocumentInfo } from '@/types/Interaction';

interface ChatState {
  interactions: InteractionInfo[];
  activeInteractionId: string | null;
  messages: ChatMessage[];
  documents: DocumentInfo[];
  
  setInteractions: (interactions: InteractionInfo[]) => void;
  setActiveInteraction: (interactionId: string | null, messages: ChatMessage[], documents: DocumentInfo[]) => void;
  addMessage: (message: ChatMessage) => void;
  addDocument: (document: DocumentInfo) => void;
  clearActiveInteraction: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  interactions: [],
  activeInteractionId: null,
  messages: [],
  documents: [],
  
  setInteractions: (interactions) => set({ interactions }),

  setActiveInteraction: (interactionId, messages, documents) => set({
    activeInteractionId: interactionId,
    messages: messages,
    documents: documents,
  }),

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message],
  })),

  addDocument: (document) => set((state) => ({
    documents: [...state.documents, document]
  })),

  clearActiveInteraction: () => set({
    activeInteractionId: null,
    messages: [],
    documents: [],
  }),
}));