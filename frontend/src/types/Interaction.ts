export interface DocumentInfo {
  id: string; 
  filename: string;
  source_type: string | null;
  created_at: string;
}


export interface ChatMessage {
  id: string; 
  role: 'user' | 'assistant';
  content: string;
  timestamp: string; 
}

export interface InteractionInfo {
  id: string;
  title: string;
  created_at: string;
  documents: DocumentInfo[];
}

export interface InteractionHistory extends InteractionInfo {
  messages: ChatMessage[];
}