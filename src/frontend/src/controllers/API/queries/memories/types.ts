export type MemoryStatus = "idle" | "generating" | "updating" | "failed";

export interface MemoryInfo {
  id: string;
  name: string;
  description?: string;
  kb_name: string;
  embedding_model: string;
  embedding_provider: string;
  is_active: boolean;
  status: MemoryStatus;
  error_message?: string;
  total_messages_processed: number;
  total_chunks: number;
  sessions_count: number;
  batch_size: number;
  preprocessing_enabled: boolean;
  preprocessing_model?: string;
  preprocessing_prompt?: string;
  pending_messages_count: number;
  user_id: string;
  flow_id: string;
  created_at?: string;
  updated_at?: string;
  last_generated_at?: string;
  documents?: MemoryDocumentItem[];
  documents_total?: number;
  document_sessions?: string[];
}

export interface MemoryDocumentItem {
  content: string;
  sender: string;
  session_id: string;
  timestamp: string;
  message_id: string;
}

export interface MemoryDocumentsResponse {
  documents: MemoryDocumentItem[];
  total: number;
  sessions: string[];
}

export interface CreateMemoryPayload {
  name: string;
  flow_id: string;
  embedding_model: string;
  embedding_provider: string;
  is_active?: boolean;
  batch_size?: number;
  preprocessing_enabled?: boolean;
  preprocessing_model?: string;
  preprocessing_prompt?: string;
  description?: string;
}

export interface UpdateMemoryPayload {
  name?: string;
  description?: string;
  is_active?: boolean;
  batch_size?: number;
  preprocessing_enabled?: boolean;
  preprocessing_model?: string;
  preprocessing_prompt?: string;
}

export type MockDb = {
  memories: Record<string, MemoryInfo>;
  documents: Record<string, MemoryDocumentItem[]>; // memoryId -> docs
};

export interface AddMessagesToMemoryParams {
  memoryId: string;
  message_ids: string[];
}

export interface DeleteMemoryParams {
  memoryId: string;
}

export interface GetMemoriesParams {
  flowId?: string;
}

export interface GetMemoryParams {
  memoryId: string;
}

export interface UpdateMemoryParams extends UpdateMemoryPayload {
  memoryId: string;
}
