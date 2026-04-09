import { useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import type { KnowledgeBaseFormData } from "@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal";

/**
 * Manages optimistic cache updates when a knowledge base is created or updated via the upload modal.
 * Call `captureSubmit` inside onSubmit, and `applyOptimisticUpdate` when the modal closes.
 */
export const useOptimisticKnowledgeBase = () => {
  const queryClient = useQueryClient();
  const lastSubmitRef = useRef<KnowledgeBaseFormData | null>(null);

  const captureSubmit = (data: KnowledgeBaseFormData) => {
    lastSubmitRef.current = data;
  };

  /**
   * Apply an optimistic cache update after the modal closes.
   * Returns `true` if files were submitted (i.e. polling should start).
   */
  const applyOptimisticUpdate = (): boolean => {
    const submitted = lastSubmitRef.current;
    if (!submitted) return false;

    const hasFiles = submitted.files && submitted.files.length > 0;
    const dirName = submitted.sourceName.trim().replace(/\s+/g, "_");
    const newStatus = hasFiles ? "ingesting" : "empty";

    queryClient.setQueryData<KnowledgeBaseInfo[]>(
      ["useGetKnowledgeBases"],
      (old) => {
        const list = old || [];
        const exists = list.some((kb) => kb.dir_name === dirName);
        if (exists) {
          // KB already in cache (add sources mode or refetch arrived early)
          return list.map((kb) =>
            kb.dir_name === dirName ? { ...kb, status: newStatus } : kb,
          );
        }
        // New KB — append optimistic entry
        return [
          ...list,
          {
            id: dirName,
            dir_name: dirName,
            name: submitted.sourceName,
            embedding_provider:
              submitted.embeddingModel?.[0]?.provider || "Unknown",
            embedding_model: submitted.embeddingModel?.[0]?.id || "Unknown",
            size: 0,
            words: 0,
            characters: 0,
            chunks: 0,
            avg_chunk_size: 0,
            status: newStatus,
            column_config: submitted.columnConfig,
          },
        ];
      },
    );

    lastSubmitRef.current = null;
    return hasFiles;
  };

  return { captureSubmit, applyOptimisticUpdate };
};
