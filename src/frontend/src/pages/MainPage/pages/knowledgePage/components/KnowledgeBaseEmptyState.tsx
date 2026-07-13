import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty-state";
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
    <Empty className="h-full w-full gap-8 pb-8">
      <EmptyHeader className="gap-2">
        <EmptyTitle className="text-2xl">
          {t("knowledge.noKnowledgeBases")}
        </EmptyTitle>
        <EmptyDescription className="text-lg text-secondary-foreground">
          {t("knowledge.emptyDescription")}
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="gap-2">
        <Button
          className="flex items-center gap-2 font-semibold"
          onClick={() => setIsUploadModalOpen(true)}
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          {t("knowledge.addKnowledge")}
        </Button>
      </EmptyContent>

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
    </Empty>
  );
};

export default KnowledgeBaseEmptyState;
