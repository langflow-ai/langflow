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
  embedding_provider?: string;
  is_active: boolean;
  total_messages_processed: number;
  sessions_count: number;
  batch_size: number;
  preprocessing_enabled: boolean;
  preprocessing_model?: string;
  preproc_instructions?: string;
  pending_messages_count: number;
  user_id: string;
  flow_id: string;
  created_at?: string;
  last_generated_at?: string;
}

export interface MemoryDocumentItem {
  content: string;
  sender: string;
  session_id: string;
  timestamp: string;
  job_id?: string;
  ingestion_timestamp?: string;
  message_id: string;
}

export interface MemorySessionInfo {
  session_id: string;
  cursor_id: string | null;
  total_processed: number;
  last_sync_at: string | null;
  id: string;
  memory_base_id: string;
  pending_count: number;
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
  messageIds: string[];
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
