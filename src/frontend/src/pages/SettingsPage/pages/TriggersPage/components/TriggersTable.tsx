import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { needsAttention } from "@/components/core/triggers/helpers/trigger-presentation";
import TriggerStatusSummary from "@/components/core/triggers/TriggerStatusSummary";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import { cn } from "@/utils/utils";
import TriggerLastEventCell from "./TriggerLastEventCell";
import TriggerSourceCell from "./TriggerSourceCell";

export type TriggersTableMode = "mine" | "all";

export interface TriggersTableProps {
  triggers: TriggerRead[];
  mode: TriggersTableMode;
  /** Connection display names by id; only the caller's own resolve. */
  connectionNames: Map<string, string>;
  busyId: string | null;
  onFix: (trigger: TriggerRead, action: "reconnect" | "resume") => void;
  renderTest?: (trigger: TriggerRead) => ReactNode;
  renderActions: (trigger: TriggerRead) => ReactNode;
}

/**
 * Settings › Triggers. One row per trigger; the state cell carries the same
 * badge, reason and fix as the node popover. The operator view swaps the
 * connection column for the owner, since other users' connections are not
 * readable.
 */
export function TriggersTable({
  triggers,
  mode,
  connectionNames,
  busyId,
  onFix,
  renderTest,
  renderActions,
}: TriggersTableProps) {
  const { t } = useTranslation();
  const operator = mode === "all";
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table className="min-w-[56rem]" data-testid={`triggers-table-${mode}`}>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">{t("triggers.columns.trigger")}</TableHead>
            {operator && (
              <TableHead scope="col">{t("triggers.columns.owner")}</TableHead>
            )}
            <TableHead scope="col">{t("triggers.columns.source")}</TableHead>
            {!operator && (
              <TableHead scope="col">
                {t("triggers.columns.connection")}
              </TableHead>
            )}
            <TableHead scope="col">{t("triggers.columns.state")}</TableHead>
            <TableHead scope="col">{t("triggers.columns.lastEvent")}</TableHead>
            {renderTest && (
              <TableHead scope="col" className="w-10">
                <span className="sr-only">{t("triggers.columns.test")}</span>
              </TableHead>
            )}
            <TableHead scope="col" className="w-10">
              <span className="sr-only">{t("triggers.columns.actions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {triggers.map((trigger) => (
            <TableRow
              key={trigger.id}
              className={cn(needsAttention(trigger) && "bg-accent-amber/20")}
              data-testid={`trigger-row-${trigger.id}`}
            >
              <TableCell>
                <div className="flex flex-col">
                  <span className="font-medium">
                    {trigger.flow_name ?? t("triggers.unknownFlow")}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {trigger.name}
                  </span>
                </div>
              </TableCell>
              {operator && (
                <TableCell>
                  {trigger.owner_username ?? (
                    <span className="text-muted-foreground">
                      {t("triggers.unknownOwner")}
                    </span>
                  )}
                </TableCell>
              )}
              <TableCell>
                <TriggerSourceCell trigger={trigger} />
              </TableCell>
              {!operator && (
                <TableCell>
                  {trigger.connection_id ? (
                    (connectionNames.get(trigger.connection_id) ?? (
                      <span className="text-muted-foreground">
                        {t("triggers.connection.unavailable")}
                      </span>
                    ))
                  ) : (
                    <span className="text-muted-foreground">
                      {t("triggers.connection.notNeeded")}
                    </span>
                  )}
                </TableCell>
              )}
              <TableCell>
                <TriggerStatusSummary
                  trigger={trigger}
                  busy={busyId === trigger.id}
                  onFix={operator ? undefined : onFix}
                />
              </TableCell>
              <TableCell>
                <TriggerLastEventCell trigger={trigger} />
              </TableCell>
              {renderTest && <TableCell>{renderTest(trigger)}</TableCell>}
              <TableCell>{renderActions(trigger)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default TriggersTable;
