import { Check, Link as LinkIcon, Plus, Settings, Trash2 } from "lucide-react";
import type { BuildTask } from "../assistant-panel.types";

interface AssistantBuildTasksProps {
  tasks: BuildTask[];
}

/**
 * Live checklist of incremental canvas mutations the agent performed inside
 * the current assistant turn. One row per task, with an icon hinting at the
 * action (add / remove / connect / configure) and a green check anchored on
 * the right since every row represents a *completed* operation — the SSE
 * event only lands after the canvas was mutated successfully.
 *
 * The component is intentionally read-only: it surfaces what the agent did.
 * Undo lives at the canvas level (Ctrl+Z), not on these bullets.
 */
export function AssistantBuildTasks({ tasks }: AssistantBuildTasksProps) {
  if (tasks.length === 0) return null;
  // No bordered box: these are pure results (completed ops, no
  // human-in-the-loop), so they render as compact lines — text with a
  // green check beside it. The card box is reserved for gated/HITL UIs.
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
    </ul>
  );
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
