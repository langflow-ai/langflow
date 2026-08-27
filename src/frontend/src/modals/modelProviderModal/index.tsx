import { useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ProviderScopeParams } from "@/controllers/API/helpers/provider-scope";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import type { ModelTypeFilter } from "@/types/models";
import ModelProvidersContent from "./components/ModelProvidersContent";

interface ModelProviderModalProps extends ProviderScopeParams {
  open: boolean;
  onClose: (opts?: { hasChanges?: boolean }) => void;
  modelType: ModelTypeFilter;
}

const ModelProviderModal = ({
  open,
  onClose,
  modelType,
  flowId,
  projectId,
}: ModelProviderModalProps) => {
  const { t } = useTranslation();
  const { refreshAllModelInputs } = useRefreshModelInputs();
  const flushRef = useRef<(() => Promise<void>) | null>(null);
  const hasChangesRef = useRef<(() => boolean) | null>(null);

  const handleClose = async () => {
    // Read the change flag synchronously BEFORE onClose unmounts the modal
    // content (which would null out the ref). When the user closes without
    // touching anything, skip both the model-input refresh and the parent's
    // post-close loading state — there's nothing to refetch.
    const hasChanges = hasChangesRef.current?.() ?? false;
    // Capture the flush promise BEFORE onClose unmounts the modal content.
    // flushPendingChanges sends any pending model toggle mutations via
    // mutateAsync and awaits the backend response, so the DB is up-to-date
    // by the time we refresh nodes below.
    const flushPromise = flushRef.current?.();
    onClose({ hasChanges });
    await flushPromise;
    if (hasChanges) {
      refreshAllModelInputs({ silent: true });
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="flex flex-col overflow-hidden rounded-xl p-0 max-w-[768px] h-[560px] gap-0">
        <DialogHeader className="flex w-full border-b px-4 py-3">
          <div className="flex justify-start items-center gap-3">
            <DialogTitle className="text-[13px] font-semibold">
              {t("modelProviders.title")}
            </DialogTitle>
          </div>
        </DialogHeader>

        <div className="h-[513px] overflow-hidden">
          <ModelProvidersContent
            key={`${flowId ?? ""}:${projectId ?? ""}`}
            modelType={modelType}
            flowId={flowId}
            projectId={projectId}
            onFlushRef={flushRef}
            onHasChangesRef={hasChangesRef}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
