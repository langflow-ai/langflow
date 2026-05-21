import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDeleteTrigger } from "@/controllers/API/queries/triggers";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import type {
  JobStatus,
  TriggerInstance,
} from "../types";
import { formatDateTime, relativeTimeFrom } from "../utils/format";

interface TriggersTableProps {
  triggers: TriggerInstance[];
  isLoading: boolean;
  selected: Set<string>;
  onSelectToggle: (key: string) => void;
  onSelectAll: (allKeys: string[], shouldSelectAll: boolean) => void;
  onViewJobs: (trigger: TriggerInstance) => void;
}

const STATUS_BADGE_VARIANT: Record<
  JobStatus,
  "default" | "successStatic" | "errorStatic" | "secondaryStatic"
> = {
  queued: "default",
  in_progress: "default",
  completed: "successStatic",
  failed: "errorStatic",
  cancelled: "secondaryStatic",
  timed_out: "errorStatic",
};

/** Stable identifier for selection state. */
export const triggerKey = (t: TriggerInstance): string =>
  `${t.flow_id}::${t.component_id}`;

export default function TriggersTable({
  triggers,
  isLoading,
  selected,
  onSelectToggle,
  onSelectAll,
  onViewJobs,
}: TriggersTableProps) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const setErrorData = useAlertStore((s) => s.setErrorData);
  const setSuccessData = useAlertStore((s) => s.setSuccessData);

  const { mutate: deleteTrigger } = useDeleteTrigger({
    onSuccess: () => setSuccessData({ title: t("triggers.deleteSuccess") }),
    onError: (err) =>
      setErrorData({
        title: t("triggers.deleteError"),
        list: [String((err as Error)?.message ?? err)],
      }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
        <ForwardedIconComponent
          name="Loader2"
          className="h-4 w-4 animate-spin"
        />
        <span className="pl-2">{t("triggers.loading")}</span>
      </div>
    );
  }

  if (triggers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <ForwardedIconComponent
          name="Clock"
          className="h-8 w-8 text-muted-foreground"
        />
        <div className="pt-3 text-sm font-medium">
          {t("triggers.emptyTitle")}
        </div>
        <div className="pt-1 text-sm text-muted-foreground">
          {t("triggers.emptyDescription")}
        </div>
      </div>
    );
  }

  const allKeys = triggers.map(triggerKey);
  const allSelected = allKeys.length > 0 && allKeys.every((k) => selected.has(k));
  const someSelected = !allSelected && allKeys.some((k) => selected.has(k));

  return (
    // ``overflow-x-auto`` contains any horizontal overflow inside the
    // table card itself so a narrow container (e.g. the drawer-open
    // layout) never propagates a page-level scroll. ``min-w-0`` works
    // with the parent flex column to allow the table to shrink below
    // its intrinsic min-content width without overflowing siblings.
    <div className="min-w-0 overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[36px]">
              <Checkbox
                data-testid="triggers-select-all"
                checked={allSelected ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={(value) => onSelectAll(allKeys, value === true)}
              />
            </TableHead>
            <TableHead>
              {t("triggers.col.flow")}
            </TableHead>
          <TableHead className="whitespace-nowrap">
            {t("triggers.col.cron")}
          </TableHead>
          <TableHead className="whitespace-nowrap">
            {t("triggers.col.timezone")}
          </TableHead>
          <TableHead className="whitespace-nowrap">
            {t("triggers.col.nextFire")}
          </TableHead>
          <TableHead className="whitespace-nowrap">
            {t("triggers.col.lastRun")}
          </TableHead>
          <TableHead className="w-[40px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {triggers.map((trigger) => {
          const key = triggerKey(trigger);
          return (
            <TableRow key={key} data-testid={`trigger-row-${key}`}>
              <TableCell>
                <Checkbox
                  data-testid={`trigger-select-${key}`}
                  checked={selected.has(key)}
                  onCheckedChange={() => onSelectToggle(key)}
                />
              </TableCell>
              <TableCell className="font-medium">
                <div className="flex min-w-0 flex-col">
                  <span className="truncate">{trigger.flow_name}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {trigger.component_id}
                  </span>
                </div>
              </TableCell>
              <TableCell>
                <code className="whitespace-nowrap rounded bg-muted px-1.5 py-0.5 text-xs">
                  {trigger.cron_expression}
                </code>
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">
                {trigger.timezone}
              </TableCell>
              <TableCell
                className="whitespace-nowrap text-sm text-muted-foreground"
                title={formatDateTime(trigger.next_fire_at)}
              >
                {relativeTimeFrom(trigger.next_fire_at)}
              </TableCell>
              <TableCell>
                {trigger.last_finished_status ? (
                  <Badge
                    variant={STATUS_BADGE_VARIANT[trigger.last_finished_status]}
                    size="xq"
                    title={formatDateTime(trigger.last_finished_at)}
                  >
                    {trigger.last_finished_status}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      data-testid={`trigger-actions-${key}`}
                    >
                      <ForwardedIconComponent
                        name="MoreHorizontal"
                        className="h-4 w-4"
                      />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => navigate(`/flow/${trigger.flow_id}`)}
                    >
                      <ForwardedIconComponent
                        name="ExternalLink"
                        className="mr-2 h-4 w-4"
                      />
                      {t("triggers.openInEditor")}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onViewJobs(trigger)}>
                      <ForwardedIconComponent
                        name="History"
                        className="mr-2 h-4 w-4"
                      />
                      {t("triggers.viewJobs")}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() =>
                        deleteTrigger({
                          flow_id: trigger.flow_id,
                          component_id: trigger.component_id,
                        })
                      }
                      className="text-destructive"
                    >
                      <ForwardedIconComponent
                        name="Trash2"
                        className="mr-2 h-4 w-4"
                      />
                      {t("triggers.delete")}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          );
        })}
        </TableBody>
      </Table>
    </div>
  );
}
