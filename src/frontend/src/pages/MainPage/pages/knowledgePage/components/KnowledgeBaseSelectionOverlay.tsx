import type { AxiosError } from "axios";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useDeleteKnowledgeBase } from "@/controllers/API/queries/knowledge-bases/use-delete-knowledge-base";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";

interface KnowledgeBaseSelectionOverlayProps {
  selectedFiles: KnowledgeBaseInfo[];
  quantitySelected: number;
  onDelete?: () => void;
  onClearSelection: () => void;
}

const KnowledgeBaseSelectionOverlay = ({
  selectedFiles,
  quantitySelected,
  onDelete,
  onClearSelection,
}: KnowledgeBaseSelectionOverlayProps) => {
  const { t } = useTranslation();
  const { setSuccessData, setErrorData } = useAlertStore((state) => ({
    setSuccessData: state.setSuccessData,
    setErrorData: state.setErrorData,
  }));

  const deleteMutation = useDeleteKnowledgeBase({
    onSuccess: (data) => {
      setSuccessData({
        title: t("knowledge.deletedCount", { count: data.deleted_count }),
      });
      onClearSelection();
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
      onClearSelection();
    },
  });

  const handleBulkDelete = () => {
    if (onDelete) {
      onDelete();
    } else {
      const knowledgeBaseDirNames = selectedFiles.map((file) => file.dir_name);
      if (knowledgeBaseDirNames.length > 0 && !deleteMutation.isPending) {
        deleteMutation.mutate({ kb_names: knowledgeBaseDirNames });
      }
    }
  };

  const isVisible = selectedFiles.length > 0;
  const pluralSuffix = quantitySelected > 1 ? "s" : "";

  return (
    <div
      className={cn(
        "pointer-events-none absolute top-1.5 z-50 flex h-8 w-full transition-opacity",
        isVisible ? "opacity-100" : "opacity-0",
      )}
    >
      <div
        className={cn(
          "ml-12 flex h-full flex-1 items-center justify-between bg-background",
          isVisible ? "pointer-events-auto" : "pointer-events-none",
        )}
      >
        <span className="text-xs text-muted-foreground">
          {t("knowledge.selected", { count: quantitySelected })}
        </span>
        <div className="flex items-center gap-2">
          <DeleteConfirmationModal
            onConfirm={handleBulkDelete}
            description={`knowledge base${pluralSuffix}`}
          >
            <Button
              variant="destructive"
              size="iconMd"
              className="px-2.5 !text-mmd"
              data-testid="bulk-delete-kb-btn"
            >
              <ForwardedIconComponent name="Trash2" />
              {t("knowledge.delete")}
            </Button>
          </DeleteConfirmationModal>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseSelectionOverlay;
