export function reportTime(
  value: string | null | undefined,
  locale: string,
  unknown: string,
): string {
  if (!value) return unknown;
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? unknown
    : new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

export function downloadReport(id: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `upgrade-report-${id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
