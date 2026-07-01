import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import {
  getKnowledgeBaseBackendLabel,
  getKnowledgeBaseBackendTarget,
} from "../utils/backendMetadata";
import IngestionRunsSection from "./IngestionRunsSection";

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

  const backendLabel = getKnowledgeBaseBackendLabel(
    knowledgeBase.backend_type,
    knowledgeBase.backend_config as Record<string, unknown> | undefined,
  );
  const backendTarget = getKnowledgeBaseBackendTarget(knowledgeBase);
  const headingId = `kb-drawer-heading-${knowledgeBase.dir_name}`;

  return (
    <div
      role="region"
      aria-labelledby={headingId}
      className="flex h-full w-80 flex-col border-l bg-background"
    >
      <div className="flex items-center justify-between pt-4 px-4">
        <h3 id={headingId} className="font-semibold">
          {knowledgeBase.name}
        </h3>
        <Button
          variant="ghost"
          size="iconSm"
          onClick={onClose}
          aria-label={t("knowledge.a11y.closeDrawer")}
        >
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
            <div className="text-sm font-medium">
              {t("knowledge.embeddingProviderLabel")}
            </div>
            <div className="text-sm font-medium text-muted-foreground">
              {knowledgeBase.embedding_provider || t("knowledge.unknown")}
            </div>
          </div>

          <div className="space-y-2 px-4">
            <div className="text-sm font-medium">
              {t("knowledge.embeddingModelLabel")}
            </div>
            <div className="text-sm font-medium text-muted-foreground">
              {knowledgeBase.embedding_model || t("knowledge.unknown")}
            </div>
          </div>

          <div className="space-y-2 px-4">
            <div className="text-sm font-medium">
              {t("knowledge.vectorStoreLabel")}
            </div>
            <div className="text-sm font-medium text-muted-foreground">
              {backendLabel}
            </div>
          </div>

          {backendTarget && (
            <div className="space-y-2 px-4">
              <div className="text-sm font-medium">
                {t("knowledge.targetLabel")}
              </div>
              <div className="text-sm font-medium text-muted-foreground">
                {backendTarget}
              </div>
            </div>
          )}

          <div className="space-y-2 px-4">
            <div className="text-sm font-medium">
              {t("knowledge.statusLabel")}
            </div>
            <div className="text-sm font-medium text-muted-foreground">
              {knowledgeBase.status || t("knowledge.unknown")}
            </div>
          </div>

          <Separator />

          <IngestionRunsSection kbName={knowledgeBase.dir_name} />
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseDrawer;
