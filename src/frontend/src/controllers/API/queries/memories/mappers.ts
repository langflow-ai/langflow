import type { GetMemoriesApiResponse, MemoryApiDTO, MemoryInfo } from "./types";

const DEFAULTS: Omit<
  MemoryInfo,
  | "id"
  | "name"
  | "kb_name"
  | "embedding_model"
  | "user_id"
  | "flow_id"
  | "created_at"
> = {
  description: undefined,
  embedding_provider: "",
  is_active: true,
  total_messages_processed: 0,
  sessions_count: 0,
  batch_size: 1,
  preprocessing_enabled: false,
  preprocessing_model: undefined,
  preproc_instructions: undefined,
  pending_messages_count: 0,
  last_generated_at: undefined,
};

export const mapMemoryApiToMemoryInfo = (dto: MemoryApiDTO): MemoryInfo => {
  return {
    ...DEFAULTS,
    id: dto.id,
    name: dto.name,
    kb_name: dto.kb_name,
    embedding_model: dto.embedding_model,
    user_id: dto.user_id,
    flow_id: dto.flow_id,
    created_at: dto.created_at,
    is_active: dto.auto_capture ?? DEFAULTS.is_active,
    preprocessing_enabled: dto.preprocessing ?? DEFAULTS.preprocessing_enabled,
    preprocessing_model: dto.preproc_model,
    preproc_instructions: dto.preproc_instructions,
    batch_size: Math.max(1, Math.trunc(dto.threshold ?? 1)),
  };
};

export const mapGetMemoriesApiResponse = (
  res: GetMemoriesApiResponse,
): {
  items: MemoryInfo[];
  total: number;
  page: number;
  size: number;
  pages: number;
} => {
  return {
    items: (res.items ?? []).map(mapMemoryApiToMemoryInfo),
    total: res.total,
    page: res.page,
    size: res.size,
    pages: res.pages,
  };
};
