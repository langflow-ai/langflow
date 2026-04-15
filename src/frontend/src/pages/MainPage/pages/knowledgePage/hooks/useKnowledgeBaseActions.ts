import { useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import { useState } from "react";
import { useCancelIngestion } from "@/controllers/API/queries/knowledge-bases/use-cancel-ingestion";
import { useDeleteKnowledgeBase } from "@/controllers/API/queries/knowledge-bases/use-delete-knowledge-base";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import useAlertStore from "@/stores/alertStore";
import { isBusyStatus } from "../config/statusConfig";

interface UseKnowledgeBaseActionsOptions {
  refetch: () => void;
  selectedFiles: KnowledgeBaseInfo[];
  clearSelection: () => void;
}

export const useKnowledgeBaseActions = ({
  refetch,
  selectedFiles,
  clearSelection,
}: UseKnowledgeBaseActionsOptions) => {
  const queryClient = useQueryClient();
  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [knowledgeBaseToDelete, setKnowledgeBaseToDelete] =
    useState<KnowledgeBaseInfo | null>(null);
  const [isBulkDeleteModalOpen, setIsBulkDeleteModalOpen] = useState(false);
  const [knowledgeBaseForAddSources, setKnowledgeBaseForAddSources] =
    useState<KnowledgeBaseInfo | null>(null);

  // --- Cancel ingestion ---

  const cancelIngestionMutation = useCancelIngestion({
    onSuccess: () => {
      setSuccessData({ title: "Ingestion cancelled" });
      refetch();
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      setErrorData({
        title: "Failed to cancel ingestion",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

  // --- Single delete ---

  const deleteKnowledgeBaseMutation = useDeleteKnowledgeBase({
    onSuccess: () => {
      setSuccessData({ title: "Knowledge base deleted" });
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      setErrorData({
        title: "Failed to delete knowledge base",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
      refetch();
    },
  });

  // --- Bulk delete ---

  const deleteKnowledgeBasesMutation = useDeleteKnowledgeBase({
    onSuccess: () => {
      setSuccessData({ title: "Knowledge base(s) deleted" });
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      setErrorData({
        title: "Failed to delete knowledge bases",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
      refetch();
    },
  });

  const deletableSelected = selectedFiles.filter(
    (kb) => !isBusyStatus(kb.status),
  );

  // --- Handlers ---

  const handleDelete = (knowledgeBase: KnowledgeBaseInfo) => {
    setKnowledgeBaseToDelete(knowledgeBase);
    setIsDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (knowledgeBaseToDelete && !deleteKnowledgeBaseMutation.isPending) {
      queryClient.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        (old) =>
          old?.filter((kb) => kb.dir_name !== knowledgeBaseToDelete.dir_name),
      );
      resetDeleteState();
      deleteKnowledgeBaseMutation.mutate({
        kb_names: knowledgeBaseToDelete.dir_name,
      });
    }
  };

  const confirmBulkDelete = () => {
    if (
      deletableSelected.length > 0 &&
      !deleteKnowledgeBasesMutation.isPending
    ) {
      const dirNames = new Set(deletableSelected.map((kb) => kb.dir_name));
      queryClient.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        (old) => old?.filter((kb) => !dirNames.has(kb.dir_name)),
      );
      clearSelection();
      setIsBulkDeleteModalOpen(false);
      deleteKnowledgeBasesMutation.mutate({
        kb_names: deletableSelected.map((kb) => kb.dir_name),
      });
    }
  };

  const handleStopIngestion = (knowledgeBase: KnowledgeBaseInfo) => {
    queryClient.setQueryData<KnowledgeBaseInfo[]>(
      ["useGetKnowledgeBases"],
      (old) =>
        old?.map((kb) =>
          kb.dir_name === knowledgeBase.dir_name
            ? { ...kb, status: "cancelling" }
            : kb,
        ),
    );
    cancelIngestionMutation.mutate({ kb_name: knowledgeBase.dir_name });
  };

  const handleAddSources = (knowledgeBase: KnowledgeBaseInfo) => {
    setKnowledgeBaseForAddSources(knowledgeBase);
  };

  const resetDeleteState = () => {
    setKnowledgeBaseToDelete(null);
    setIsDeleteModalOpen(false);
  };

  return {
    // Modal state
    isDeleteModalOpen,
    setIsDeleteModalOpen,
    knowledgeBaseToDelete,
    isBulkDeleteModalOpen,
    setIsBulkDeleteModalOpen,
    knowledgeBaseForAddSources,
    setKnowledgeBaseForAddSources,
    deletableSelected,

    // Handlers
    handleDelete,
    confirmDelete,
    confirmBulkDelete,
    handleStopIngestion,
    handleAddSources,
  };
};
