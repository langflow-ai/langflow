import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

interface KnowledgeBaseDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  knowledgeBase: KnowledgeBaseInfo | null;
}

const KnowledgeBaseDrawer = ({
  isOpen,
  onClose,
  knowledgeBase,
}: KnowledgeBaseDrawerProps) => {
  const { t } = useTranslation();
  if (!isOpen || !knowledgeBase) {
    return null;
  }

  return (
    <div className="flex h-full w-80 flex-col border-l bg-background">
      <div className="flex items-center justify-between pt-4 px-4">
        <h3 className="font-semibold">{knowledgeBase.name}</h3>
        <Button variant="ghost" size="iconSm" onClick={onClose}>
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto pt-3">
        <div className="flex flex-col gap-4">
          <div className="px-4">
            <div className="text-sm text-muted-foreground">
              {t("knowledge.noDescription")}
            </div>
          </div>

          <Separator />

          <div className="space-y-2 px-4">
            <label className="text-sm font-medium">{t("knowledge.embeddingProviderLabel")}</label>
            <div className="flex items-center gap-2">
              <div className="text-sm font-medium text-muted-foreground">
                {knowledgeBase.embedding_model || t("knowledge.embeddingModelUnknown")}
              </div>
            </div>
          </div>

          <div className="space-y-3 px-4">
            <h4 className="text-sm font-medium">{t("knowledge.sourceFilesLabel")}</h4>
            <div className="text-sm text-muted-foreground">
              {t("knowledge.noSourceFiles")}
            </div>
          </div>

          <div className="space-y-3 px-4">
            <h4 className="text-sm font-medium">{t("knowledge.linkedFlowsLabel")}</h4>
            <div className="text-sm text-muted-foreground">
              {t("knowledge.noLinkedFlows")}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseDrawer;
