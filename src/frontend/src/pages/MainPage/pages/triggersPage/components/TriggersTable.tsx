import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  useDeleteTrigger,
  usePatchTrigger,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { Trigger } from "../types";

interface TriggersTableProps {
  triggers: Trigger[];
  isLoading: boolean;
  onEdit: (trigger: Trigger) => void;
  onViewJobs: (trigger: Trigger) => void;
}

export default function TriggersTable({
  triggers,
  isLoading,
  onEdit,
  onViewJobs,
}: TriggersTableProps) {
  const { t } = useTranslation();
  const flows = useFlowsManagerStore((s) => s.flows);
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

  const { mutate: patchTrigger } = usePatchTrigger({
    onError: (err) =>
      setErrorData({
        title: t("triggers.toggleError"),
        list: [String((err as Error)?.message ?? err)],
      }),
  });

  const flowNameById = (id: string) =>
    flows?.find((f) => f.id === id)?.name ?? id;

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

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("triggers.col.name")}</TableHead>
          <TableHead>{t("triggers.col.flow")}</TableHead>
          <TableHead>{t("triggers.col.cron")}</TableHead>
          <TableHead>{t("triggers.col.timezone")}</TableHead>
          <TableHead>{t("triggers.col.status")}</TableHead>
          <TableHead className="w-[40px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {triggers.map((trigger) => (
          <TableRow key={trigger.id} data-testid={`trigger-row-${trigger.id}`}>
            <TableCell className="font-medium">{trigger.name}</TableCell>
            <TableCell className="text-muted-foreground">
              {flowNameById(trigger.flow_id)}
            </TableCell>
            <TableCell>
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {trigger.cron_expression ?? "—"}
              </code>
            </TableCell>
            <TableCell className="text-muted-foreground">
              {trigger.timezone}
            </TableCell>
            <TableCell>
              <Badge
                variant={trigger.is_active ? "successStatic" : "secondary"}
                className="cursor-pointer"
                onClick={() =>
                  patchTrigger({
                    trigger_id: trigger.id,
                    patch: { is_active: !trigger.is_active },
                  })
                }
              >
                {trigger.is_active
                  ? t("triggers.statusActive")
                  : t("triggers.statusInactive")}
              </Badge>
            </TableCell>
            <TableCell>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    data-testid={`trigger-actions-${trigger.id}`}
                  >
                    <ForwardedIconComponent
                      name="MoreHorizontal"
                      className="h-4 w-4"
                    />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onViewJobs(trigger)}>
                    <ForwardedIconComponent
                      name="History"
                      className="mr-2 h-4 w-4"
                    />
                    {t("triggers.viewJobs")}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onEdit(trigger)}>
                    <ForwardedIconComponent
                      name="Pencil"
                      className="mr-2 h-4 w-4"
                    />
                    {t("triggers.edit")}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => deleteTrigger({ trigger_id: trigger.id })}
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
        ))}
      </TableBody>
    </Table>
  );
}
