import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  runUpgradeCheck,
  type UpgradeCheckEvent,
  useGetUpgradeReleases,
} from "@/controllers/API/queries/upgrade-reports";

type Run =
  | { kind: "idle" }
  | {
      kind: "running";
      target: string;
      checked: number;
      total: number | null;
      download: boolean;
    }
  | {
      kind: "done";
      target: string;
      download: boolean;
      flows: { ok: number; warn: number; fail: number } | null;
    }
  | { kind: "failed"; code: string; message: string };

const KNOWN_CODES = [
  "invalid_target_version",
  "check_running",
  "uvx_unavailable",
  "check_failed",
  "install_failed",
  "timeout",
  "import_refused",
  "invalid_upgrade_report",
  "connection_lost",
];

// Downloading and loading components give no count, so the bar only moves once flows are checked.
// Saved versions that still run come on top of the total, so past it the bar stops counting.
function Progress({ run }: { run: Extract<Run, { kind: "running" }> }) {
  const { t } = useTranslation();
  const { checked, total } = run;
  const measured = total !== null && checked > 0 && checked <= total;
  return (
    <div className="space-y-2">
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={t("settings.upgrade.check.progress")}
        aria-valuemin={measured ? 0 : undefined}
        aria-valuemax={measured ? total : undefined}
        aria-valuenow={measured ? checked : undefined}
      >
        <div
          className={
            measured
              ? "h-full rounded-full bg-primary transition-[width] duration-500 motion-reduce:transition-none"
              : "h-full w-full animate-pulse rounded-full bg-primary/40 motion-reduce:animate-none"
          }
          style={measured ? { width: `${(checked / total) * 100}%` } : {}}
        />
      </div>
      <p role="status">
        {checked === 0
          ? t(
              run.download
                ? "settings.upgrade.check.downloading"
                : "settings.upgrade.check.checking",
              { version: run.target },
            )
          : measured
            ? t("settings.upgrade.check.checkedOf", { checked, count: total })
            : t("settings.upgrade.check.checked", { count: checked })}
      </p>
    </div>
  );
}

// The report opens further down the page, so this says it is ready, what it found, and what comes next.
function Done({ run }: { run: Extract<Run, { kind: "done" }> }) {
  const { t, i18n } = useTranslation();
  const { flows } = run;
  const clean = flows !== null && flows.warn + flows.fail === 0;
  const next = run.download
    ? clean
      ? "nextUpgradeClean"
      : "nextUpgradeFlagged"
    : clean
      ? "nextCurrentClean"
      : "nextCurrentFlagged";
  const count = (value: number) => value.toLocaleString(i18n.language);
  const view = () => {
    const heading = document.getElementById("upgrade-report-title");
    heading?.scrollIntoView({ behavior: "smooth", block: "start" });
    heading?.focus({ preventScroll: true });
  };
  return (
    <div className="space-y-3 rounded-md border bg-muted/40 p-3">
      <div role="status" className="space-y-1">
        <p className="font-medium">
          {t("settings.upgrade.check.done.title", { version: run.target })}
        </p>
        {flows && (
          <p className="text-sm">
            {[
              `${t("settings.upgrade.status.ok")}: ${count(flows.ok)}`,
              `${t("settings.upgrade.status.warn")}: ${count(flows.warn)}`,
              `${t("settings.upgrade.status.fail")}: ${count(flows.fail)}`,
            ].join(" · ")}
          </p>
        )}
        <p className="text-sm">
          {t(`settings.upgrade.check.done.${next}`, { version: run.target })}
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={view} ignoreTitleCase>
        {t("settings.upgrade.check.done.view")}
      </Button>
    </div>
  );
}

export default function RunCheck({
  onImported,
}: {
  onImported: (reportId: string) => void;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const releases = useGetUpgradeReleases();
  const [target, setTarget] = useState("");
  const [run, setRun] = useState<Run>({ kind: "idle" });
  const controller = useRef<AbortController | null>(null);
  // Leaving the page cancels the check on the server.
  // A refusal also ends in an abort, so only dropping the ref marks a run as cancelled.
  const stop = () => {
    const current = controller.current;
    controller.current = null;
    current?.abort();
  };
  useEffect(() => stop, []);

  const start = async () => {
    const version = target.trim();
    const abort = new AbortController();
    controller.current = abort;
    setRun({
      kind: "running",
      target: version,
      checked: 0,
      total: null,
      download: true,
    });
    let finished = false;
    const refused = await runUpgradeCheck({
      targetVersion: version,
      controller: abort,
      onEvent: (event: UpgradeCheckEvent) => {
        if (event.event === "started") {
          setRun({
            kind: "running",
            target: event.target_version,
            checked: 0,
            total: event.total ?? null,
            download: event.download,
          });
        } else if (event.event === "flow") {
          setRun((now) =>
            now.kind === "running" ? { ...now, checked: now.checked + 1 } : now,
          );
        } else if (event.event === "imported") {
          finished = true;
          client.invalidateQueries({ queryKey: ["useGetUpgradeReports"] });
          setRun((now) => ({
            kind: "done",
            target: now.kind === "running" ? now.target : version,
            download: now.kind === "running" ? now.download : true,
            flows: event.flows ?? null,
          }));
          onImported(event.report_id);
        } else if (event.event === "error") {
          finished = true;
          setRun({
            kind: "failed",
            code: event.code,
            message: event.message ?? "",
          });
        }
      },
    });
    const cancelled = controller.current !== abort;
    if (!cancelled) controller.current = null;
    if (finished || cancelled) return;
    setRun(
      refused && refused.status !== 0
        ? {
            kind: "failed",
            code: refused.code ?? "refused",
            message: refused.message ?? "",
          }
        : { kind: "failed", code: "connection_lost", message: "" },
    );
  };

  const running = run.kind === "running";
  return (
    <section
      aria-labelledby="upgrade-check-title"
      className="min-w-0 space-y-3 rounded-lg border p-4"
    >
      <h3 id="upgrade-check-title" className="font-medium">
        {t("settings.upgrade.check.title")}
      </h3>
      <p className="text-sm text-muted-foreground">
        {t("settings.upgrade.check.help")}
      </p>
      <label className="flex flex-col gap-2">
        {t("settings.upgrade.check.target")}
        <input
          list="upgrade-check-releases"
          value={target}
          disabled={running}
          aria-invalid={run.kind === "failed"}
          aria-describedby="upgrade-check-feedback"
          autoComplete="off"
          spellCheck={false}
          className="w-full min-w-0 max-w-full rounded-md border border-input bg-background p-2 text-sm"
          onChange={(event) => {
            setTarget(event.target.value);
            if (run.kind === "failed" || run.kind === "done")
              setRun({ kind: "idle" });
          }}
        />
        <datalist id="upgrade-check-releases">
          {(releases.data?.releases ?? []).map((version) => (
            <option key={version} value={version} />
          ))}
        </datalist>
      </label>
      <div className="flex gap-2">
        <Button
          disabled={running || !target.trim()}
          onClick={start}
          ignoreTitleCase
        >
          {t("settings.upgrade.check.run")}
        </Button>
        {running && (
          <Button
            variant="outline"
            onClick={() => {
              stop();
              setRun({ kind: "idle" });
            }}
            ignoreTitleCase
          >
            {t("settings.upgrade.check.cancel")}
          </Button>
        )}
      </div>
      <div id="upgrade-check-feedback">
        {run.kind === "running" && <Progress run={run} />}
        {run.kind === "done" && <Done run={run} />}
        {run.kind === "failed" && (
          <p role="alert">
            {KNOWN_CODES.includes(run.code)
              ? t(`settings.upgrade.check.error.${run.code}`)
              : run.message || t("settings.upgrade.check.error.refused")}
            {KNOWN_CODES.includes(run.code) &&
              ["check_failed", "install_failed"].includes(run.code) &&
              run.message && (
                <code className="mt-1 block whitespace-pre-wrap break-words text-xs">
                  {run.message}
                </code>
              )}
          </p>
        )}
      </div>
    </section>
  );
}
