import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import type { TriggerEventRead } from "@/controllers/API/queries/triggers";

const TraceDetailView = lazy(() =>
  import("@/pages/FlowPage/components/TraceComponent/TraceDetailView").then(
    (module) => ({ default: module.TraceDetailView }),
  ),
);

export default function TriggerRunDialog({
  event,
  flowName,
  onOpenChange,
}: {
  event: TriggerEventRead;
  flowName: string;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent
        className="h-[85vh] max-w-6xl gap-0 overflow-hidden p-0"
        data-testid="trigger-run-dialog"
      >
        <DialogTitle className="sr-only">{t("trace.traceDetails")}</DialogTitle>
        <DialogDescription className="sr-only">{flowName}</DialogDescription>
        <Suspense fallback={<p role="status">{t("trace.loadingTrace")}</p>}>
          <TraceDetailView
            traceId={event.job_id}
            flowName={flowName}
            pollUpdates={
              event.state === "claimed" || event.state === "dispatched"
            }
          />
        </Suspense>
      </DialogContent>
    </Dialog>
  );
}
