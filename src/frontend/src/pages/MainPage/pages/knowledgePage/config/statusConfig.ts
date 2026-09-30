export interface StatusConfigEntry {
  label: string;
  textClass: string;
}

export const STATUS_CONFIG: Record<string, StatusConfigEntry> = {
  ready: {
    label: "knowledge.status.ready",
    textClass: "text-accent-emerald-foreground",
  },
  ingesting: {
    label: "knowledge.status.ingesting",
    textClass: "text-accent-amber-foreground",
  },
  failed: {
    label: "knowledge.status.failed",
    textClass: "text-destructive",
  },
  cancelling: {
    label: "knowledge.status.cancelling",
    textClass: "text-accent-amber-foreground",
  },
  empty: {
    label: "knowledge.status.empty",
    textClass: "text-muted-foreground",
  },
};

export const BUSY_STATUSES = ["ingesting", "cancelling"] as const;

export const isBusyStatus = (status?: string): boolean =>
  BUSY_STATUSES.includes(status as (typeof BUSY_STATUSES)[number]);
