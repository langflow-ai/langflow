export type MemoryStatus = "idle" | "generating" | "updating" | "failed";

export interface MemoryApiDTO {
  id: string;
  name: string;
  flow_id: string;
  user_id: string;
  threshold: number;
  auto_capture: boolean;
  embedding_model: string;
  preprocessing: boolean;
  preproc_model?: string;
  preproc_instructions?: string;
  kb_name: string;
  created_at: string;
}

export interface GetMemoriesApiResponse {
  items: MemoryApiDTO[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

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

export interface CreateMemoryPayload {
  name: string;
  flow_id: string;
  embedding_model: string;
  threshold?: number;
  auto_capture?: boolean;
  preprocessing?: boolean;
  preproc_model?: string;
  preproc_instructions?: string;
}

export interface UpdateMemoryPayload {
  name?: string;
  embedding_model?: string;
  preproc_model?: string;
  preproc_instructions?: string;
  threshold?: number;
  auto_capture?: boolean;
  preprocessing?: boolean;
}

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
