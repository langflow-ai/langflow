import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { TraceView } from "@/modals/flowLogsModal/components/TraceView";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

interface RunTracePanelProps {
  selectedRunId: string | null;
  onClose: () => void;
}

export function RunTracePanel({ selectedRunId, onClose }: RunTracePanelProps) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  return (
    <Sheet
      open={!!selectedRunId}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent
        className="w-[85vw] max-w-[85vw] bg-background p-0 sm:max-w-[85vw] [&>button]:z-10"
        style={{ top: "48px", height: "calc(100vh - 48px)" }}
      >
        <SheetTitle className="sr-only">Trace Detail</SheetTitle>
        <SheetDescription className="sr-only">
          Detailed trace view for the selected run
        </SheetDescription>
        <div className="flex h-full flex-col overflow-hidden">
          <TraceView
            flowId={currentFlowId}
            initialTraceId={selectedRunId}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
