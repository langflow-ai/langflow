export function reportAssessment(
  incomplete: boolean,
  failures: number,
  warnings: number,
) {
  if (incomplete) return "incomplete";
  if (failures) return "blocked";
  if (warnings) return "review";
  return "clear";
}

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

export function reportAge(
  value: string | null | undefined,
  locale: string,
  unknown: string,
  now = Date.now(),
): string {
  if (!value) return unknown;
  const elapsed = Date.parse(value) - now;
  if (!Number.isFinite(elapsed)) return unknown;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["week", 7 * 24 * 60 * 60 * 1000],
    ["day", 24 * 60 * 60 * 1000],
    ["hour", 60 * 60 * 1000],
    ["minute", 60 * 1000],
    ["second", 1000],
  ];
  const [unit, duration] =
    units.find(([, duration]) => Math.abs(elapsed) >= duration) ?? units[4];
  return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(
    Math.trunc(elapsed / duration),
    unit,
  );
}

export function downloadReport(id: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `upgrade-report-${id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const archivedReplacements: Record<string, string> = {
  "files_and_knowledge.Knowledge": "Knowledge",
  "models_and_agents.Agent": "Agent",
  "mrscraper.MrscraperFetchHtml": "MrScraper Scraper API",
};

export function reportReason({
  code,
  message,
}: {
  code: string;
  message: string | null;
}): string {
  if (code !== "retired" || !message) return message ?? code;
  return message.replace(
    /[\w]+\.[\w]+/g,
    (reference) => archivedReplacements[reference] ?? reference,
  );
}
