import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useGetTriggerJobs } from "@/controllers/API/queries/triggers";
import type { JobStatus, TriggerInstance, TriggerJob } from "../types";
import { formatDateTime } from "../utils/format";

interface TriggerJobsDrawerProps {
  trigger: TriggerInstance;
  onClose: () => void;
}

const STATUS_BADGE: Record<
  JobStatus,
  { variant: "default" | "successStatic" | "errorStatic" | "secondaryStatic"; label: string }
> = {
  queued: { variant: "default", label: "queued" },
  in_progress: { variant: "default", label: "in_progress" },
  completed: { variant: "successStatic", label: "completed" },
  failed: { variant: "errorStatic", label: "failed" },
  cancelled: { variant: "secondaryStatic", label: "cancelled" },
  timed_out: { variant: "errorStatic", label: "timed_out" },
};

/**
 * Two-column row inside the job card: a fixed-width muted label on
 * the left, a non-wrapping monospace value on the right. Used for
 * every timestamp so the dates stay on one line and the labels
 * stay visually aligned across rows.
 */
function TimestampRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className="truncate whitespace-nowrap font-mono text-xs">
        {value}
      </span>
    </div>
  );
}

function JobCard({ job }: { job: TriggerJob }) {
  const badge = STATUS_BADGE[job.status];
  return (
    <div className="flex flex-col gap-1.5 border-b px-4 py-3 hover:bg-muted/50">
      <div className="flex items-center justify-between gap-2">
        <Badge variant={badge.variant} size="xq">
          {badge.label}
        </Badge>
        <span className="whitespace-nowrap text-xs text-muted-foreground">
          attempt {job.attempt}/{job.max_attempts}
        </span>
      </div>
      <TimestampRow label="scheduled" value={formatDateTime(job.scheduled_at)} />
      {job.started_at && (
        <TimestampRow label="started" value={formatDateTime(job.started_at)} />
      )}
      {job.finished_at && (
        <TimestampRow label="finished" value={formatDateTime(job.finished_at)} />
      )}
      {job.error && (
        <div className="mt-1 rounded bg-error-background px-2 py-1 text-xs text-error-foreground break-words">
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
  // Poll every 5s — aligned with the worker's idle backoff cap so a
  // fresh fire becomes visible within seconds without a manual reload.
  const { data: jobs, isLoading } = useGetTriggerJobs(
    { flowId: trigger.flow_id, componentId: trigger.component_id, limit: 20 },
    { refetchInterval: 5000 },
  );

  return (
    <div className="flex h-full w-96 flex-col border-l bg-background">
      {/*
        Header: flow name on the first line, component id under it.
        Both ``truncate`` so a long flow name (e.g. "New Flow
        (Backup)") never forces a line break that pushes the close
        button down. The close button stays pinned at the same
        vertical position as the title.
      */}
      <div className="flex items-start justify-between gap-2 px-4 pt-4">
        <div className="flex min-w-0 flex-col">
          <h3 className="truncate text-sm font-semibold">
            {trigger.flow_name}
          </h3>
          <span className="truncate text-xs text-muted-foreground">
            {trigger.component_id}
          </span>
        </div>
        <Button
          variant="ghost"
          size="iconSm"
          onClick={onClose}
          className="-mr-1 -mt-1 shrink-0"
        >
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
          jobs.map((job) => <JobCard key={job.id} job={job} />)
        )}
      </div>
    </div>
  );
}
