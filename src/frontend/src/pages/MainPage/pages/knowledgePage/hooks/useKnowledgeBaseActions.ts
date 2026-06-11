import { useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import { useState } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
      setSuccessData({ title: t("success.ingestionCancelled") });
      refetch();
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      setErrorData({
        title: t("errors.failedToCancelIngestion"),
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            t("knowledge.unknownError"),
        ],
      });
    },
  });

  // --- Single delete ---

  const deleteKnowledgeBaseMutation = useDeleteKnowledgeBase({
    onSuccess: () => {
      setSuccessData({ title: t("success.knowledgeBaseDeleted") });
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      setErrorData({
        title: t("errors.failedToDeleteKnowledgeBase"),
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            t("knowledge.unknownError"),
        ],
      });
      refetch();
    },
  });

  // --- Bulk delete ---

  const deleteKnowledgeBasesMutation = useDeleteKnowledgeBase({
    onSuccess: () => {
      setSuccessData({ title: t("success.knowledgeBaseDeleted") });
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      setErrorData({
        title: t("knowledge.failedToDelete"),
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            t("knowledge.unknownError"),
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
