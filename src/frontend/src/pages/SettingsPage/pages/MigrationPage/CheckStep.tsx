import { useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type MigrationCheck,
  type MigrationError,
  type MigrationState,
  migrationKeys,
  runSourceChecks,
  useAcceptFindingMutation,
  useWithdrawFindingMutation,
} from "@/controllers/API/queries/migration";
import { cn } from "@/utils/utils";
import {
  acceptanceOf,
  CHECK_TOTAL,
  CHECKS,
  formatTime,
  groupChecks,
  STEP_SLUGS,
} from "./catalog";

const VERSION_FIELD = "migration-target-version";

/** The body of "Check this instance": the version field, the run, and the grouped results. */
export function CheckStep({ migration }: { migration: MigrationState }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const run = migration.record.steps.check_source;
  // The admin's own last entry, never this instance's version.
  const [version, setVersion] = useState(migration.record.target.version ?? "");
  const [versionError, setVersionError] = useState<MigrationError>();
  const [startFailed, setStartFailed] = useState(false);
  const [running, setRunning] = useState(false);
  const [streamed, setStreamed] = useState<MigrationCheck[]>([]);
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => () => controller.current?.abort(), []);
  // Focus carries the refused version's error to a screen reader.
  useEffect(() => {
    if (versionError) input.current?.focus();
  }, [versionError]);
  useEffect(() => {
    if (!running) return;
    const guard = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [running]);

  const start = async () => {
    setVersionError(undefined);
    setStartFailed(false);
    setStreamed([]);
    setRunning(true);
    controller.current = new AbortController();
    let started = false;
    const refused = await runSourceChecks({
      targetVersion: version,
      controller: controller.current,
      onEvent: (event) => {
        // The record says running once the stream starts, so the step's marker and summary follow it.
        if (!started) {
          started = true;
          queryClient.invalidateQueries({ queryKey: migrationKeys.all });
        }
        if (event.event === "check") {
          setStreamed((previous) => [...previous, event.check]);
        }
      },
    });
    await queryClient.invalidateQueries({ queryKey: migrationKeys.all });
    setRunning(false);
    // Another admin's run (409) shows once the record is read again.
    if (refused?.status === 422) setVersionError(refused.detail);
    else if (refused && refused.status !== 409) setStartFailed(true);
  };

  const busy = !running && run?.status === "running";
  const blocked = migration.blocking_findings.length > 0;
  const checks = running ? streamed : (run?.report?.checks ?? []);
  const groups = groupChecks(checks, migration.acceptable_findings);
  const lastRun =
    run &&
    t("settings.migration.check.lastRun", {
      time: formatTime(run.finished_at, i18n.language),
      user: run.started_by,
      version: run.target_version,
    });

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!running && !busy) start();
        }}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor={VERSION_FIELD}>
            {t("settings.migration.check.version.label")}
          </Label>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
            <div className="flex-1">
              <Input
                ref={input}
                id={VERSION_FIELD}
                className="aria-[invalid=true]:border-destructive"
                value={version}
                placeholder={migration.instance.version}
                readOnly={running || busy}
                onChange={(event) => {
                  setVersion(event.target.value);
                  setVersionError(undefined);
                }}
                aria-invalid={Boolean(versionError)}
                aria-describedby={
                  versionError
                    ? `${VERSION_FIELD}-error ${VERSION_FIELD}-help`
                    : `${VERSION_FIELD}-help`
                }
                data-testid={VERSION_FIELD}
              />
            </div>
            {running ? (
              <Button
                type="button"
                variant="outline"
                className="w-full shrink-0 sm:w-fit"
                onClick={() => controller.current?.abort()}
                ignoreTitleCase
              >
                {t("settings.migration.check.stop")}
              </Button>
            ) : (
              <Button
                type="submit"
                className="w-full shrink-0 sm:w-fit"
                disabled={busy}
                ignoreTitleCase
                data-testid="migration-run-checks"
              >
                {run
                  ? t("settings.migration.check.runAgain")
                  : t("settings.migration.check.run")}
              </Button>
            )}
          </div>
          {versionError && (
            <p
              id={`${VERSION_FIELD}-error`}
              className="text-sm text-destructive"
            >
              {versionError.code === "version_older"
                ? t("settings.migration.check.version.older", {
                    version:
                      versionError.source_version ?? migration.instance.version,
                  })
                : t("settings.migration.check.version.invalid", {
                    version: migration.instance.version,
                  })}
            </p>
          )}
          <p
            id={`${VERSION_FIELD}-help`}
            className="text-xs text-muted-foreground"
          >
            {t("settings.migration.check.version.help")}
          </p>
        </div>
        {(running || !run) && (
          <p className="text-sm text-muted-foreground">
            {t("settings.migration.check.note")}
          </p>
        )}
      </form>

      {/* Stays in the accessibility tree while empty, so the first progress line and the outcome are read. */}
      <div aria-live="polite" className="flex flex-col gap-4 empty:-mt-4">
        {running && (
          <p className="text-sm text-muted-foreground">
            {t("settings.migration.check.running", {
              done: streamed.length,
              total: CHECK_TOTAL,
            })}
          </p>
        )}
        {busy && (
          <p className="text-sm text-muted-foreground">
            {t("settings.migration.check.busy", { user: run?.started_by })}
          </p>
        )}
        {!running && run?.status === "cancelled" && (
          <p className="text-sm">{t("settings.migration.check.stopped")}</p>
        )}
        {!running && run?.status === "done" && (
          <div
            className={cn(
              "flex items-start gap-3 rounded-md border p-3",
              blocked
                ? "border-destructive/50"
                : "border-accent-emerald-foreground/40",
            )}
            data-testid="migration-checks-summary"
          >
            <ForwardedIconComponent
              name={blocked ? "CircleAlert" : "CircleCheck"}
              className={cn(
                "mt-0.5 h-4 w-4 shrink-0",
                blocked ? "text-destructive" : "text-accent-emerald-foreground",
              )}
              aria-hidden="true"
            />
            <div className="flex flex-col gap-0.5">
              <p
                className={cn(
                  "text-sm font-medium",
                  blocked
                    ? "text-destructive"
                    : "text-accent-emerald-foreground",
                )}
              >
                {blocked
                  ? t("settings.migration.check.blocking", {
                      count: migration.blocking_findings.length,
                    })
                  : t("settings.migration.check.clear")}
              </p>
              <p className="text-xs text-muted-foreground">{lastRun}</p>
            </div>
          </div>
        )}
      </div>

      {!running && (startFailed || run?.status === "failed") && (
        <Alert variant="destructive">
          <AlertDescription className="flex flex-col gap-2">
            {t("settings.migration.check.failed")}
            {!startFailed && run?.error && <Details text={run.error} />}
          </AlertDescription>
        </Alert>
      )}

      {(["fix", "decide", "read"] as const).map(
        (group) =>
          groups[group].length > 0 && (
            <section
              key={group}
              className="flex flex-col"
              data-testid={`migration-group-${group}`}
            >
              <h5 className="text-sm font-semibold">
                {t(`settings.migration.group.${group}`)}
              </h5>
              <p className="text-xs text-muted-foreground">
                {t(`settings.migration.group.${group}Hint`)}
              </p>
              <ul className="flex flex-col divide-y">
                {groups[group].map((check) => (
                  <CheckRow
                    key={check.name}
                    check={check}
                    migration={migration}
                    acceptable={group === "decide" && !running}
                  />
                ))}
              </ul>
            </section>
          ),
      )}
      {groups.passed.length > 0 && (
        <details data-testid="migration-group-passed">
          <summary className="cursor-pointer text-sm font-semibold">
            {t("settings.migration.group.passed", {
              count: groups.passed.length,
            })}
          </summary>
          <ul className="flex flex-col divide-y">
            {groups.passed.map((check) => (
              <li
                key={check.name}
                className="flex flex-col gap-1 py-2"
                data-testid={`migration-check-${check.name}`}
              >
                <span className="text-sm">{checkTitle(t, check)}</span>
                <Details
                  text={checkDetails(check)}
                  title={checkTitle(t, check)}
                />
              </li>
            ))}
          </ul>
        </details>
      )}
      {groups.notRun && (
        <p className="text-sm text-muted-foreground">
          {t("settings.migration.check.notRun")}
        </p>
      )}
    </div>
  );
}

function CheckRow({
  check,
  migration,
  acceptable,
}: {
  check: MigrationCheck;
  migration: MigrationState;
  acceptable: boolean;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const acceptFinding = useAcceptFindingMutation();
  const withdrawFinding = useWithdrawFindingMutation();
  const [problem, setProblem] = useState<"changed" | "saveFailed">();
  const known = CHECKS[check.name];
  const acceptance = acceptanceOf(check, migration.record.accepted_findings);
  const accepted = Boolean(acceptance && !acceptance.lapsed);
  const acceptId = `migration-accept-${check.name}`;
  const pending = acceptFinding.isPending || withdrawFinding.isPending;

  const decide = (accept: boolean) => {
    setProblem(undefined);
    (accept ? acceptFinding : withdrawFinding).mutate(check.name, {
      onError: (error) => {
        const detail = (error as AxiosError<{ detail?: MigrationError }>)
          .response?.data?.detail;
        if (detail?.code !== "not_failing") {
          setProblem("saveFailed");
          return;
        }
        setProblem("changed");
        queryClient.invalidateQueries({ queryKey: migrationKeys.all });
      },
    });
  };

  return (
    <li
      className="flex flex-col gap-1 py-3"
      data-testid={`migration-check-${check.name}`}
    >
      <span
        className={cn(
          "text-sm font-medium",
          accepted && "text-muted-foreground",
        )}
      >
        {checkTitle(t, check)}
      </span>
      {known && (
        <p className="text-sm text-muted-foreground">
          {t(`settings.migration.check.${known.slug}.body`)}
        </p>
      )}
      {check.status === "warn" && known?.handledIn && (
        <Badge variant="secondaryStatic" size="sm" className="w-fit">
          {t("settings.migration.check.handledIn", {
            step: t(
              `settings.migration.step.${STEP_SLUGS[known.handledIn]}.title`,
            ),
          })}
        </Badge>
      )}
      <Details
        text={checkDetails(check)}
        title={checkTitle(t, check)}
        open={!known}
      />
      {acceptable && (
        <div className="flex items-center gap-2 pt-1">
          {/* aria-disabled, since native disabled would drop the keyboard user's focus to <body>. */}
          <Checkbox
            id={acceptId}
            checked={accepted}
            aria-disabled={pending}
            className="aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
            onCheckedChange={(value) => {
              if (!pending) decide(value === true);
            }}
          />
          <Label htmlFor={acceptId} className="text-sm font-normal">
            {known?.accept ? (
              t(`settings.migration.check.${known.slug}.accept`)
            ) : (
              <span lang="en">{check.name}</span>
            )}
          </Label>
        </div>
      )}
      {acceptable && acceptance && (
        <p
          className={cn(
            "text-xs",
            acceptance.lapsed ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {acceptance.lapsed
            ? t("settings.migration.check.lapsed", {
                user: acceptance.finding.accepted_by,
              })
            : t("settings.migration.check.acceptedBy", {
                user: acceptance.finding.accepted_by,
                time: formatTime(acceptance.finding.accepted_at, i18n.language),
              })}
        </p>
      )}
      <p role="status" className="text-xs text-destructive empty:-mt-1">
        {problem && t(`settings.migration.check.${problem}`)}
      </p>
    </li>
  );
}

/** The backend's own words for a check, or a command's output, in English. */
function Details({
  text,
  title,
  open,
}: {
  text: string;
  /** Names the check for a screen reader, since every row has its own Details. */
  title?: ReactNode;
  open?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <details open={open} className="text-xs">
      <summary className="cursor-pointer text-muted-foreground">
        {t("settings.migration.check.details")}
        {title && <span className="sr-only">, {title}</span>}
      </summary>
      <pre
        lang="en"
        className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-2 font-mono text-xs"
      >
        {text}
      </pre>
    </details>
  );
}

const checkTitle = (
  t: ReturnType<typeof useTranslation>["t"],
  check: MigrationCheck,
): ReactNode =>
  CHECKS[check.name] ? (
    t(`settings.migration.check.${CHECKS[check.name].slug}.title`)
  ) : (
    // The backend's own name, in English.
    <span lang="en">{check.name}</span>
  );

const checkDetails = (check: MigrationCheck) =>
  [check.summary, ...check.problems].join("\n");
