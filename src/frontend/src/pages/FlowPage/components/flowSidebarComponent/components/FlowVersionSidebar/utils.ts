import { uiLocale } from "@/utils/format-date";

export function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString(uiLocale(), {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Reason slugs the OSS backend writes to `retained_reason`. Other values
// (for example from an extension) are shown as written.
// A Map, so a reason such as "toString" never matches an Object prototype key.
const PROTECTED_REASON_KEYS = new Map<string, string>([
  ["evaluation", "version.protectedReason.evaluation"],
  ["admin-upgrade-repair", "version.protectedReason.upgradeRepair"],
]);

/** Tells the user why a retained version is protected from deletion. */
export function protectedReasonText(
  reason: string | null | undefined,
  t: (key: string, options?: Record<string, string>) => string,
): string {
  const trimmed = reason?.trim().replace(/\.+$/, "");
  if (!trimmed) return t("version.protectedReason.unknown");
  const key = PROTECTED_REASON_KEYS.get(trimmed);
  return key ? t(key) : t("version.protectedReason.other", { reason: trimmed });
}
