export interface StatusConfigEntry {
  label: string;
  textClass: string;
}

export const STATUS_CONFIG: Record<string, StatusConfigEntry> = {
  ready: {
    label: "Ready",
    textClass: "text-emerald-600 dark:text-emerald-400",
  },
  ingesting: {
    label: "Ingesting",
    textClass: "text-amber-600 dark:text-amber-400",
  },
  failed: {
    label: "Failed",
    textClass: "text-red-600 dark:text-red-400",
  },
  cancelling: {
    label: "Cancelling",
    textClass: "text-orange-600 dark:text-orange-400",
  },
  empty: {
    label: "Empty",
    textClass: "text-zinc-500 dark:text-zinc-400",
  },
};

export const BUSY_STATUSES = ["ingesting", "cancelling"] as const;

export const isBusyStatus = (status?: string): boolean =>
  BUSY_STATUSES.includes(status as (typeof BUSY_STATUSES)[number]);
