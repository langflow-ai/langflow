import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import type { FlowType } from "@/types/flow";
import { cn } from "@/utils/utils";

interface ProjectFlowPickerProps {
  flows: FlowType[];
  isLoading: boolean;
  /** Ids of the flows currently picked. */
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
}

/**
 * Picks flows out of the project.
 *
 * The canvas widgets all edit one component's input, so none of them can answer "which flows in
 * this project can the agent call". A project type asks for this one by name
 * (`renders: "project_flows"`), and the composition is the point: every flow that lives here is
 * on the list, and the switches say which ones the agent gets.
 */
export const ProjectFlowPicker = ({
  flows,
  isLoading,
  value,
  onChange,
  disabled = false,
}: ProjectFlowPickerProps) => {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const picked = new Set(value);
  const filteredFlows = flows.filter((flow) =>
    `${flow.name} ${flow.description ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const missing = value.filter((id) => !flows.some((flow) => flow.id === id));

  const toggle = (flowId: string) => {
    const next = new Set(picked);
    if (next.has(flowId)) {
      next.delete(flowId);
    } else {
      next.add(flowId);
    }
    // Keep the project's own order rather than click order, so the saved list is stable.
    onChange([
      ...flows.filter((flow) => next.has(flow.id)).map((flow) => flow.id),
      ...missing,
    ]);
  };

  if (isLoading) {
    return (
      <div
        className="flex flex-col gap-1"
        data-testid="flow-picker-loading"
        aria-busy="true"
      >
        {[0, 1, 2].map((row) => (
          <div key={row} className="flex items-center gap-3 p-3">
            <Skeleton className="h-9 w-9 shrink-0 rounded-lg" />
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-56" />
            </div>
            <Skeleton className="h-6 w-11 rounded-full" />
          </div>
        ))}
      </div>
    );
  }

  if (flows.length === 0 && !missing.length) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-muted/30 px-6 py-8 text-center"
        data-testid="flow-picker-empty"
      >
        <ForwardedIconComponent
          name="Workflow"
          aria-hidden="true"
          className="h-5 w-5 text-muted-foreground"
        />
        <span className="text-mmd font-medium">
          {t("harness.noFlowsTitle")}
        </span>
        <span className="max-w-sm text-xs text-muted-foreground">
          {t("harness.noFlowsDescription")}
        </span>
      </div>
    );
  }

  const allPicked =
    filteredFlows.length > 0 &&
    filteredFlows.every((flow) => picked.has(flow.id));

  return (
    <div className="flex flex-col gap-2" data-testid="flow-picker">
      <p className="text-sm text-muted-foreground">{t("harness.toolsHelp")}</p>
      {flows.length > 5 && (
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t("harness.searchTools")}
          aria-label={t("harness.searchTools")}
          disabled={disabled}
        />
      )}
      {missing.length > 0 && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted p-3 text-sm"
          role="status"
        >
          <span>
            {t("harness.toolsUnavailable", { count: missing.length })}
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={disabled}
            onClick={() =>
              onChange(value.filter((id) => !missing.includes(id)))
            }
          >
            {t("harness.removeUnavailable")}
          </Button>
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {t("harness.toolsPickedCount", {
            count: picked.size,
            total: flows.length,
          })}
        </span>
        <Button
          unstyled
          data-testid="flow-picker-toggle-all"
          className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          onClick={() =>
            onChange(
              allPicked
                ? value.filter(
                    (id) => !filteredFlows.some((flow) => flow.id === id),
                  )
                : [
                    ...flows
                      .filter(
                        (flow) =>
                          picked.has(flow.id) || filteredFlows.includes(flow),
                      )
                      .map((flow) => flow.id),
                    ...missing,
                  ],
            )
          }
          disabled={disabled || !filteredFlows.length}
        >
          {allPicked ? t("harness.toolsClearAll") : t("harness.toolsSelectAll")}
        </Button>
      </div>

      <div className="flex flex-col gap-1">
        {filteredFlows.map((flow) => {
          const isPicked = picked.has(flow.id);
          return (
            <div
              key={flow.id}
              data-testid={`flow-picker-row-${flow.id}`}
              className={cn(
                "flex w-full min-w-0 items-center gap-3 rounded-lg px-3 py-3 text-left",
                isPicked ? "bg-muted" : "hover:bg-muted/60",
              )}
            >
              <div
                className={cn(
                  "flex h-6 w-6 flex-shrink-0 items-center justify-center text-muted-foreground",
                )}
              >
                <ForwardedIconComponent
                  name={flow.icon || "Workflow"}
                  aria-hidden="true"
                  className="h-4 w-4"
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">
                  {flow.name}
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {flow.description || t("harness.toolNoDescription")}
                </p>
              </div>

              <Switch
                data-testid={`flow-picker-switch-${flow.id}`}
                checked={isPicked}
                disabled={disabled}
                onCheckedChange={() => toggle(flow.id)}
                aria-label={t("harness.toolToggleLabel", { name: flow.name })}
              />
            </div>
          );
        })}
      </div>
      {!filteredFlows.length && search && (
        <p className="py-4 text-sm text-muted-foreground">
          {t("harness.noMatchingTools")}
        </p>
      )}
    </div>
  );
};

export default ProjectFlowPicker;
