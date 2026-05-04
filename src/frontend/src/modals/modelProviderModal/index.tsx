import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import ModelProvidersContent from "./components/ModelProvidersContent";

interface ModelProviderModalProps {
  open: boolean;
  onClose: (opts?: { hasChanges?: boolean }) => void;
  modelType: "llm" | "embeddings" | "all";
}

const ModelProviderModal = ({
  open,
  onClose,
  modelType,
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
            <div className="text-[13px] font-semibold">
              {t("modelProviders.title")}
            </div>
          </div>
        </DialogHeader>

        <div className="h-[513px] overflow-hidden">
          <ModelProvidersContent
            modelType={modelType}
            onFlushRef={flushRef}
            onHasChangesRef={hasChangesRef}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
