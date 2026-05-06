import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import KnowledgeBaseUploadModal from "@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal";
import useAlertStore from "@/stores/alertStore";
import { useOptimisticKnowledgeBase } from "../hooks/useOptimisticKnowledgeBase";

const KnowledgeBaseEmptyState = ({
  handleCreateKnowledge,
}: {
  handleCreateKnowledge: () => void;
}) => {
  const { t } = useTranslation();
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { captureSubmit, applyOptimisticUpdate } = useOptimisticKnowledgeBase();

  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
      <div className="flex flex-col items-center gap-2">
        <h3 className="text-2xl font-semibold">
          {t("knowledge.noKnowledgeBases")}
        </h3>
        <p className="text-lg text-secondary-foreground">
          {t("knowledge.emptyDescription")}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button
          className="flex items-center gap-2 font-semibold"
          onClick={() => setIsUploadModalOpen(true)}
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          {t("knowledge.addKnowledge")}
        </Button>
      </div>

      <KnowledgeBaseUploadModal
        open={isUploadModalOpen}
        setOpen={(open) => {
          setIsUploadModalOpen(open);
          if (!open) {
            applyOptimisticUpdate();
          }
        }}
        onSubmit={(data) => {
          captureSubmit(data);
          setSuccessData({
            title: t("knowledge.baseCreated", { name: data.sourceName }),
          });
        }}
      />
    </div>
  );
};

export default KnowledgeBaseEmptyState;
