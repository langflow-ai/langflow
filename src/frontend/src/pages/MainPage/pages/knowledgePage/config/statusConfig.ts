export interface StatusConfigEntry {
  label: string;
  textClass: string;
}

export const STATUS_CONFIG: Record<string, StatusConfigEntry> = {
  ready: {
    label: "Ready",
    textClass: "text-accent-emerald-foreground",
  },
  ingesting: {
    label: "Ingesting",
    textClass: "text-accent-amber-foreground",
  },
  failed: {
    label: "Failed",
    textClass: "text-destructive",
  },
  cancelling: {
    label: "Cancelling",
    textClass: "text-accent-amber-foreground",
  },
  empty: {
    label: "Empty",
    textClass: "text-muted-foreground",
  },
};

export const BUSY_STATUSES = ["ingesting", "cancelling"] as const;

export const isBusyStatus = (status?: string): boolean =>
  BUSY_STATUSES.includes(status as (typeof BUSY_STATUSES)[number]);
