export interface DocumentInfo {
  id: string; 
  filename: string;
  source_type: string | null;
  created_at: string;
}

export interface InteractionInfo {
  id: string;
  title: string;
  created_at: string;
  documents: DocumentInfo[];
}