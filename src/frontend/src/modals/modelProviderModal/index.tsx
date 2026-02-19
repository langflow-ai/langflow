import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import ModelProvidersContent from "./components/ModelProvidersContent";

interface ModelProviderModalProps {
  open: boolean;
  onClose: () => void;
  modelType: "llm" | "embeddings" | "all";
}

const ModelProviderModal = ({
  open,
  onClose,
  modelType,
}: ModelProviderModalProps) => {
  const { refreshAllModelInputs } = useRefreshModelInputs();

  const handleClose = () => {
    onClose();
    setTimeout(() => {
      refreshAllModelInputs({ silent: true });
    }, 1000);
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="flex flex-col overflow-hidden rounded-xl p-0 max-w-[768px] h-[560px] gap-0">
        <DialogHeader className="flex w-full border-b px-4 py-3">
          <div className="flex justify-start items-center gap-3">
            <div className="text-[13px] font-semibold">Model providers</div>
          </div>
        </DialogHeader>

        <div className="h-[513px] overflow-hidden">
          <ModelProvidersContent modelType={modelType} />
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
