export function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
