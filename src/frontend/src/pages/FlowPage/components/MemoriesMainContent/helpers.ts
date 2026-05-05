export const statusColors: Record<string, string> = {
  idle: "text-muted-foreground",
  generating: "text-primary",
  updating: "text-primary",
  failed: "text-destructive",
};

export const statusBgColors: Record<string, string> = {
  idle: "bg-muted",
  generating: "bg-primary/10",
  updating: "bg-primary/10",
  failed: "bg-destructive/10",
};

export const formatDate = (dateStr?: string) => {
  if (!dateStr) return "Never";
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
};

export const formatTimestamp = (ts?: string) => {
  if (!ts) return "-";
  try {
    const normalized = ts.includes("T") ? ts : ts.replace(" ", "T");
    const d = new Date(normalized);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
};
