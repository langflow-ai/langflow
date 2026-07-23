import type { ContentType } from "@/types/chat";

export type ToolStatus = "running" | "done" | "error";

/** Derives a tool's visible status from the data the producer already sets.
 * An `error` payload wins (even with a duration, an errored tool shouldn't
 * look successful); a `duration` means the step resolved; otherwise the
 * call is still in flight. */
export function getToolStatus(content: ContentType): ToolStatus {
  if (content.type === "tool_use" && content.error != null) {
    return "error";
  }
  if (content.duration !== undefined) {
    return "done";
  }
  return "running";
}

/** Tailwind classes for the small status dot on the accordion trigger. */
export const TOOL_STATUS_CLASS: Record<ToolStatus, string> = {
  running: "bg-primary animate-pulse",
  done: "bg-accent-emerald-foreground",
  error: "bg-destructive",
};
