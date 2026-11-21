import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import Loading from "@/components/ui/loading";
import type { TriggerEventRead } from "@/controllers/API/queries/triggers";
import { isEventRunning } from "./event-helpers";

const TraceDetailView = lazy(() =>
  import("@/pages/FlowPage/components/TraceComponent/TraceDetailView").then(
    (module) => ({ default: module.TraceDetailView }),
  ),
);

function RunInProgress() {
  const { t } = useTranslation();
  return (
    <div
      className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center"
      role="status"
      data-testid="trigger-run-in-progress"
    >
      <Loading size={32} className="text-primary" />
      <p className="text-sm font-medium">
        {t("triggers.events.runInProgress")}
      </p>
      <p className="text-sm text-muted-foreground">
        {t("triggers.events.runInProgressHint")}
      </p>
    </div>
  );
}

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
        {/* The trace is written when the run ends; until then it would 404.
            Once the polled event leaves the running states, the view mounts
            and loads the finished trace. */}
        {isEventRunning(event) ? (
          <RunInProgress />
        ) : (
          <Suspense fallback={<p role="status">{t("trace.loadingTrace")}</p>}>
            <TraceDetailView traceId={event.job_id} flowName={flowName} />
          </Suspense>
        )}
      </DialogContent>
    </Dialog>
  );
}
