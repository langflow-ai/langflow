import {
  Check,
  CircleAlert,
  Link as LinkIcon,
  Loader2,
  Plus,
  Settings,
  Trash2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { BuildTask, InProgressBuildTask } from "../assistant-panel.types";

type Translate = ReturnType<typeof useTranslation>["t"];

interface AssistantBuildTasksProps {
  tasks: BuildTask[];
  /** The mutating tool currently executing — rendered as a spinner row. */
  inProgressTask?: InProgressBuildTask;
  /** True when the run failed: the in-progress row freezes with an alert icon
   * so the user sees exactly where the agent stopped. */
  hasError?: boolean;
}

/**
 * Live checklist of incremental canvas mutations the agent performed inside
 * the current assistant turn. One row per task, with an icon hinting at the
 * action (add / remove / connect / configure) and a green check anchored on
 * the right since every row represents a *completed* operation — the SSE
 * event only lands after the canvas was mutated successfully.
 *
 * While a mutating tool is still executing, a trailing spinner row shows the
 * live "currently doing X" state from the ``tool_start`` SSE event; the row
 * disappears when the matching completed task arrives or the run ends.
 *
 * The component is intentionally read-only: it surfaces what the agent did.
 * Undo lives at the canvas level (Ctrl+Z), not on these bullets.
 */
export function AssistantBuildTasks({
  tasks,
  inProgressTask,
  hasError = false,
}: AssistantBuildTasksProps) {
  const { t } = useTranslation();
  if (tasks.length === 0 && !inProgressTask) return null;
  // No bordered box: pure results render as compact lines with a green
  // check — the card box is reserved for gated/HITL UIs.
  return (
    <ul className="my-2 flex flex-col gap-1">
      {tasks.map((task) => (
        <li
          key={`${task.action}-${
            task.componentId ?? `${task.sourceId}->${task.targetId}`
          }-${task.receivedAt}`}
          data-testid={`assistant-build-task-${task.action}-${
            task.componentId ?? task.sourceId ?? "unknown"
          }`}
          className="flex items-center gap-2 text-sm text-muted-foreground"
        >
          {renderIcon(task)}
          <span>{renderLabel(task)}</span>
          <Check className="h-3.5 w-3.5 text-accent-emerald-foreground" />
        </li>
      ))}
      {inProgressTask && (
        <li
          data-testid="assistant-build-task-in-progress"
          className="flex items-center gap-2 text-sm text-muted-foreground"
        >
          {hasError ? (
            <CircleAlert className="h-3.5 w-3.5 text-destructive" />
          ) : (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          )}
          <span>{inProgressLabel(t, inProgressTask)}</span>
        </li>
      )}
    </ul>
  );
}

function inProgressLabel(t: Translate, task: InProgressBuildTask): string {
  switch (task.tool) {
    case "add_component":
      return t("assistant.buildTasks.inProgress.adding", {
        name:
          task.componentType ?? t("assistant.buildTasks.inProgress.component"),
      });
    case "remove_component":
      return t("assistant.buildTasks.inProgress.removing", {
        name:
          task.componentId ?? t("assistant.buildTasks.inProgress.component"),
      });
    case "connect_components":
      return t("assistant.buildTasks.inProgress.wiring");
    case "configure_component":
      return t("assistant.buildTasks.inProgress.configuring", {
        name:
          task.componentId ?? t("assistant.buildTasks.inProgress.component"),
      });
    case "build_flow":
      return t("assistant.buildTasks.inProgress.buildingFlow");
    case "propose_field_edit":
      return t("assistant.buildTasks.inProgress.proposingEdit");
    case "use_template":
      return t("assistant.buildTasks.inProgress.applyingTemplate");
    default:
      // Unknown future tools: prefer the backend's English label over a blank row.
      return task.label ?? t("assistant.buildTasks.inProgress.working");
  }
}

function renderIcon(task: BuildTask) {
  const className = "h-3.5 w-3.5 text-muted-foreground";
  switch (task.action) {
    case "add_component":
      return <Plus className={className} />;
    case "remove_component":
      return <Trash2 className={className} />;
    case "connect":
      return <LinkIcon className={className} />;
    case "configure":
      return <Settings className={className} />;
  }
}

function renderLabel(task: BuildTask) {
  switch (task.action) {
    case "add_component":
      return `Added ${task.componentType ?? task.componentId ?? "component"}`;
    case "remove_component":
      return `Removed ${task.componentId ?? "component"}`;
    case "connect":
      return `Wired ${task.sourceId ?? "source"} → ${task.targetId ?? "target"}`;
    case "configure":
      return `Configured ${task.componentId ?? "component"}`;
  }
}
