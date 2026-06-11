import i18n from "@/i18n";

export const formatDate = (dateStr?: string) => {
  if (!dateStr) return i18n.t("memory.never");
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const formatTimestamp = (ts?: string) => {
  if (!ts) return "-";
  const trimmed = ts.trim();
  const normalized = (() => {
    if (trimmed.includes("T")) return trimmed;
    const parts = trimmed.split(/\s+/g);
    if (parts.length < 2) return trimmed;
    return `${parts[0]}T${parts.slice(1).join("")}`;
  })();
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};
