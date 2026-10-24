// Contracts mirror FastAPI/Pydantic. Backend remains authoritative for validation and access.
export type ID = string;
export type Role = "owner" | "admin" | "member";
export interface User {
  id: ID;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
}
export interface Workspace {
  id: ID;
  name: string;
  description: string | null;
  owner_id: ID;
  created_at: string;
  updated_at: string;
}
export interface Member {
  id: ID;
  workspace_id: ID;
  user_id: ID;
  role: Role;
  joined_at: string;
}
export interface Document {
  id: ID;
  workspace_id: ID;
  uploaded_by: ID;
  original_filename: string;
  mime_type: string | null;
  file_size: number | null;
  checksum_sha256: string;
  processing_status: "pending" | "processing" | "completed" | "failed";
  processing_error: string | null;
  processing_attempts: number;
  last_processed_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface IndexStatus {
  ready_for_research?: boolean;
  indexing_complete?: boolean;
  research_blocker?: string | null;
  indexing_blocker?: string | null;
  document_id: ID;
  embedding_model: string;
  dimensions: number;
  state: "not_indexed" | "queued" | "running" | "done" | "failed";
  generation: string | null;
  attempts: number;
  total_chunks: number;
  indexed_chunks: number;
  current_generation_chunks: number;
  error: string | null;
  last_attempt_at: string | null;
}
export interface Claim {
  claim_id: string;
  text: string;
  citation_ids: string[];
}
export interface Citation {
  citation_id: string;
  document_id: ID | null;
  chunk_id: ID | null;
  filename: string;
  page_number: number | null;
  section: string | null;
  source_ref: string;
  supporting_excerpt: string;
  char_start: number;
  char_end: number;
  claim_ids?: string[];
}
export interface SavedCitation extends Citation {
  id: ID;
  original_document_id: ID;
  original_chunk_id: ID;
  ordering: number;
  validation_metadata: {
    method?: string;
    validated_at?: string;
    claim_ids?: string[];
  };
}
export type AnswerStatus =
  | "answered"
  | "insufficient_evidence"
  | "retrieval_unavailable"
  | "provider_error";
export interface Usage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}
export interface Answer {
  answer: string;
  status: AnswerStatus;
  reason: string;
  claims: Claim[];
  citations: Citation[];
  retrieved_evidence_count: number;
  model_identifier: string | null;
  usage: Usage | null;
  request_id: string;
}
export interface Conversation {
  id: ID;
  workspace_id: ID;
  owner_id: ID;
  title: string;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  archived_at: string | null;
}
export interface Message {
  id: ID;
  conversation_id: ID;
  role: "user" | "assistant";
  content: string;
  sequence: number;
  created_at: string;
  generation_status: "pending" | "completed" | "failed";
  answer_status: AnswerStatus | null;
  reason: string | null;
  model_identifier: string | null;
  usage: Usage | null;
  claims: Claim[];
  retrieved_evidence_count: number;
  request_id: string | null;
  generation_http_status: number | null;
  citations: SavedCitation[];
}
export interface ConversationPage {
  items: Conversation[];
  next_cursor: ID | null;
}
export interface MessagePage {
  items: Message[];
  next_after_sequence: number | null;
}
export interface Turn {
  user_message: Message;
  assistant_message: Message;
  replayed: boolean;
}
export interface Question {
  mode?: "question" | "summary" | "comparison";
  question: string;
  document_ids?: ID[] | null;
  retrieval_limit?: number;
}
export interface SearchResult {
  chunk_id: ID;
  document_id: ID;
  filename: string;
  excerpt: string;
  page_number: number | null;
  section: string | null;
  source_ref: string;
  similarity: number;
  embedding_model: string;
}

export interface ChunkPage {
  items: {
    chunk_id: ID;
    chunk_index: number;
    excerpt: string;
    page_number: number | null;
    section: string | null;
    source_ref: string;
    char_start: number;
    char_end: number;
    truncated: boolean;
  }[];
  next_offset: number | null;
}
export interface ResearchStatus {
  documents: number;
  processing_complete: number;
  indexing_complete: number;
  ready_for_research: number;
  embedding_profile: string;
  providers: Record<
    "embedding" | "llm",
    {
      provider: string;
      model: string;
      configured: boolean;
      offline: boolean;
      blocker: string | null;
      live_access: string;
    }
  >;
}
