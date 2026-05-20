import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useGetTriggerJobs } from "@/controllers/API/queries/triggers";
import type { JobStatus, Trigger, TriggerJob } from "../types";

interface TriggerJobsDrawerProps {
  trigger: Trigger;
  onClose: () => void;
}

const STATUS_BADGE: Record<
  JobStatus,
  { variant: "successStatic" | "errorStatic" | "secondaryStatic" | "default"; label: string }
> = {
  queued: { variant: "default", label: "queued" },
  in_progress: { variant: "default", label: "in_progress" },
  completed: { variant: "successStatic", label: "completed" },
  failed: { variant: "errorStatic", label: "failed" },
  cancelled: { variant: "secondaryStatic", label: "cancelled" },
  timed_out: { variant: "errorStatic", label: "timed_out" },
};

function formatTime(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function JobRow({ job }: { job: TriggerJob }) {
  const badge = STATUS_BADGE[job.status];
  return (
    <div className="flex flex-col gap-1 px-4 py-3 hover:bg-muted/50">
      <div className="flex items-center justify-between">
        <Badge variant={badge.variant} size="xq">
          {badge.label}
        </Badge>
        <span className="text-xs text-muted-foreground">
          attempt {job.attempt}/{job.max_attempts}
        </span>
      </div>
      <div className="text-xs text-muted-foreground">
        scheduled: {formatTime(job.scheduled_at)}
      </div>
      {job.started_at && (
        <div className="text-xs text-muted-foreground">
          started: {formatTime(job.started_at)}
        </div>
      )}
      {job.finished_at && (
        <div className="text-xs text-muted-foreground">
          finished: {formatTime(job.finished_at)}
        </div>
      )}
      {job.error && (
        <div className="mt-1 rounded bg-error-background px-2 py-1 text-xs text-error-foreground">
          {job.error}
        </div>
      )}
    </div>
  );
}

export default function TriggerJobsDrawer({
  trigger,
  onClose,
}: TriggerJobsDrawerProps) {
  const { t } = useTranslation();
  // Refetch every 5s while the drawer is open so a freshly-fired job
  // shows up without manual reload. Aligned with the worker's max
  // idle backoff so latency between fire and visible is bounded.
  const { data: jobs, isLoading } = useGetTriggerJobs(
    { triggerId: trigger.id, limit: 20 },
    { refetchInterval: 5000 },
  );

  return (
    <div className="flex h-full w-80 flex-col border-l bg-background">
      <div className="flex items-center justify-between px-4 pt-4">
        <h3 className="text-sm font-semibold">{trigger.name}</h3>
        <Button variant="ghost" size="iconSm" onClick={onClose}>
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>
      <div className="px-4 pb-3 pt-1 text-xs text-muted-foreground">
        {t("triggers.jobsDrawerTitle")}
      </div>
      <Separator />
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
            <ForwardedIconComponent
              name="Loader2"
              className="h-4 w-4 animate-spin"
            />
          </div>
        ) : !jobs || jobs.length === 0 ? (
          <div className="px-4 py-8 text-center text-xs text-muted-foreground">
            {t("triggers.jobsEmpty")}
          </div>
        ) : (
          jobs.map((job) => <JobRow key={job.id} job={job} />)
        )}
      </div>
    </div>
  );
}
