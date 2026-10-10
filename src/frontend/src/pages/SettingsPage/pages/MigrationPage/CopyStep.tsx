import { useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  type CopyDecision,
  type CopyEvent,
  type CopyItem,
  type CopyStepId,
  followCopy,
  type MigrationCopyRun,
  type MigrationError,
  type MigrationState,
  type MigrationStepState,
  migrationKeys,
  useDecideMutation,
  useStartCopyMutation,
  useStopCopyMutation,
} from "@/controllers/API/queries/migration";
import ConfirmationModal from "@/modals/confirmationModal";
import { Details } from "./CheckStep";
import {
  COPIES,
  COPY_CODES,
  copyCounts,
  copyProgress,
  DECISIONS,
  formatTime,
  ITEM_CODES,
  STEP_SLUGS,
} from "./catalog";

// How long the page waits before it asks again for a run whose connection dropped.
const RETRY_MS = 2000;

/** The body of a copy step: start the copy, follow it while it runs, stop it, and say how the last one went. */
export function CopyStep({
  migration,
  state,
  step,
}: {
  migration: MigrationState;
  state: MigrationStepState;
  step: CopyStepId;
}) {
  const { t, i18n } = useTranslation();
  const run = migration.record.steps[step];
  const progress = useProgress(step, run);
  const start = useStartCopyMutation(step);
  const stop = useStopCopyMutation(step);
  // One choice is sent at a time, and how it went is the step's to show: the list it was made on may be gone.
  const decide = useDecideMutation();
  const [confirming, setConfirming] = useState(false);
  const { body, stopBody, testRun } = COPIES[step];
  // The step a refusal sends the admin back to.
  const destinations = t(
    `settings.migration.step.${STEP_SLUGS.connect_target}.title`,
  );
  const line = (code = "") =>
    t(`settings.migration.${COPY_CODES[code] ?? "error.crashed"}`, {
      step: destinations,
    });
  const refusal = start.error?.response?.data?.detail?.code ?? "";
  // The server starts a copy only when every step before it is done or skipped. A copy that ran keeps its
  // place when one of them opens again, so the page offers no start until that step is finished.
  const place = migration.steps.findIndex(({ id }) => id === step);
  const reached = migration.steps
    .slice(0, place)
    .every((earlier) => ["done", "skipped"].includes(earlier.state));
  // The state can close the gate under a focused start button: a refused start reads it again, and so does the
  // poll. The button is then gone and the browser drops focus on <body>, so focus goes to the line in its place.
  const gate = useRef<HTMLParagraphElement>(null);
  const focused = useRef(false);
  useEffect(() => {
    if (reached || !focused.current) return;
    focused.current = false;
    if (!document.activeElement || document.activeElement === document.body)
      gate.current?.focus();
  }, [reached]);
  const running = run?.status === "running";
  const [key, counts] = progress
    ? copyProgress(step, progress, i18n.language)
    : ["copy.starting", {}];
  // Whether this page watched the run, so it has an end to announce.
  const [followed, setFollowed] = useState(false);
  useEffect(() => {
    if (running) setFollowed(true);
  }, [running]);
  // The step's row shows the result. This says it too, to a screen reader that waited on the copy.
  const finished =
    followed && step === "copy_database" && state.state === "done"
      ? t("settings.migration.copyDb.done", {
          tables: run?.report?.tables_copied?.toLocaleString(i18n.language),
          rows: run?.report?.rows_copied?.toLocaleString(i18n.language),
        })
      : "";

  // The command's own words for a run that did not count.
  const said =
    run?.error?.message ??
    run?.report?.problems?.map((problem) => problem.message).join("\n");
  // Why the last copy does not count. A test run blocks nothing, so one that could not finish says why here.
  const code =
    state.state === "blocked"
      ? state.reason
      : run?.dry_run
        ? run.error?.code
        : undefined;
  // A copy that ended in a step that waits again no longer counts, so it is history. A test run never counted.
  const stale = state.state === "current" && Boolean(run) && !run?.dry_run;
  // What the last run found. A copy that is history has no result to show.
  const report = stale ? undefined : run?.report;
  const items = report?.attention ?? [];
  const counted = copyCounts(report?.counts);
  const count = (value: number) => value.toLocaleString(i18n.language);
  // The record keeps the first of the failed items. With more than it keeps, the server offers no acceptance.
  const cut = counted.failed > items.length;
  // An item is accepted in the copy that left it. A test run left nothing.
  const acceptable = !run?.dry_run;
  // The decision that accepts an item, where the server offers one. One that names no item is an option, asked below.
  const acceptance = (item: CopyItem) =>
    acceptable && item.decision?.subject && DECISIONS[item.decision.kind]
      ? item.decision
      : undefined;
  // What the copy asked before it would go on. A copy that is history asks nothing.
  const asked = stale ? undefined : run?.decision_needed;
  // An option holds for the whole copy, so the items that wait for one share a single question.
  const options = new Map(
    items.flatMap(({ decision }) =>
      decision && decision.subject === null
        ? [[decision.kind, decision] as const]
        : [],
    ),
  );

  return (
    <div className="flex flex-col items-start gap-3">
      {!running && (
        <>
          <p className="text-sm text-muted-foreground">
            {t(`settings.migration.${body}`)}
          </p>
          {step === "copy_knowledge_bases" &&
            migration.instance.database.type === "postgresql" && (
              <p className="text-sm">
                {t("settings.migration.kb.postgresNote")}
              </p>
            )}
          {stale && (
            <p className="text-sm">{t("settings.migration.copy.stale")}</p>
          )}
        </>
      )}
      {/* One region for both states, so what a run found is read out as well as its progress. */}
      <p
        role="status"
        aria-live="polite"
        className={
          running
            ? "text-sm text-muted-foreground"
            : report?.counts
              ? "text-sm"
              : "sr-only"
        }
      >
        {running
          ? t(`settings.migration.${key}`, counts)
          : report?.counts
            ? t(
                `settings.migration.copy.${run?.dry_run ? "testCounts" : "counts"}`,
                {
                  copied: count(counted.copied),
                  skipped: count(counted.skipped),
                  failed: count(counted.failed),
                },
              )
            : finished}
      </p>
      {running ? (
        <>
          {stop.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t("settings.migration.failed")}
            </p>
          )}
          <Button
            variant="outline"
            size="sm"
            loading={stop.isPending}
            onClick={() => setConfirming(true)}
            ignoreTitleCase
          >
            {t("settings.migration.check.stop")}
          </Button>
          <ConfirmationModal
            open={confirming}
            onClose={() => setConfirming(false)}
            onCancel={() => setConfirming(false)}
            title={t("settings.migration.copy.stopTitle")}
            cancelText={t("modal.cancelButton")}
            confirmationText={t("settings.migration.check.stop")}
            onConfirm={() => {
              setConfirming(false);
              stop.mutate(run.run_id);
            }}
            size="x-small"
          >
            <ConfirmationModal.Content>
              {t(`settings.migration.${stopBody}`)}
            </ConfirmationModal.Content>
          </ConfirmationModal>
        </>
      ) : (
        <>
          {code && (
            <div role="alert" className="flex flex-col gap-1 text-sm">
              <p className="text-destructive">
                {/* What stops the step is one of the items below, which says so itself. */}
                {items.some((item) => item.code === code)
                  ? t("settings.migration.copy.attention")
                  : line(code)}
              </p>
              {said && <Details text={said} />}
            </div>
          )}
          {asked?.details?.orphans && (
            <div className="flex flex-col gap-2 text-sm">
              <p>{t("settings.migration.copyDb.orphans.body")}</p>
              <ul className="list-disc pl-5">
                {asked.details.orphans.map((orphan) => (
                  <li key={`${orphan.table}.${orphan.column}`}>
                    {/* A SET NULL row is copied with its key cleared, not left out. */}
                    {t(
                      `settings.migration.copyDb.orphans.${orphan.ondelete === "SET NULL" ? "rowCleared" : "row"}`,
                      {
                        table: orphan.table,
                        column: orphan.column,
                        parent: orphan.parent,
                        rows: count(orphan.rows),
                      },
                    )}
                  </li>
                ))}
              </ul>
              {asked.decision && (
                <Decision
                  step={step}
                  decision={asked.decision}
                  decide={decide}
                />
              )}
            </div>
          )}
          {replaced(decide.error) && (
            // The state is read again after a refusal, so what follows is the list of the copy that took its place.
            <p role="alert" className="text-sm text-destructive">
              {t("settings.migration.copy.reportChanged")}
            </p>
          )}
          {items.some(acceptance) && (
            // The check may have asked about the same loss, so the step says why this copy asks again.
            <p className="text-sm text-muted-foreground">
              {t("settings.migration.copy.acceptNote", {
                step: t(
                  `settings.migration.step.${STEP_SLUGS.check_source}.title`,
                ),
              })}
            </p>
          )}
          {items.length > 0 && (
            <ul className="flex w-full flex-col gap-2 text-sm">
              {items.map((item, index) => {
                const name = item.kb_name ?? item.file_name;
                const accept = acceptance(item);
                return (
                  <li
                    // Two chat messages that miss the same file are two items with one subject.
                    key={`${item.subject} ${index}`}
                    className="flex flex-col gap-1 rounded-md border p-3"
                  >
                    <span className="break-words">
                      <span className="font-medium">{name}</span>{" "}
                      <span className="text-muted-foreground">
                        ({item.owner})
                      </span>
                    </span>
                    <span>
                      {t(
                        `settings.migration.${ITEM_CODES[item.code ?? ""] ?? "error.notCopied"}`,
                        { step: destinations },
                      )}
                    </span>
                    {item.reason && <Details text={item.reason} title={name} />}
                    {accept && (
                      <Decision
                        step={step}
                        decision={accept}
                        name={name}
                        decide={decide}
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {[...options.values()].map((decision) => (
            <Decision
              key={decision.kind}
              step={step}
              decision={decision}
              decide={decide}
            />
          ))}
          {cut && (
            <div className="text-xs text-muted-foreground">
              <p>
                {t("settings.migration.copy.attentionMore", {
                  shown: count(items.length),
                  count: count(counted.failed),
                })}
              </p>
              <p>{t("settings.migration.copy.tooManyToAccept")}</p>
            </div>
          )}
          {reached ? (
            <>
              {start.isError && (
                <p role="alert" className="text-sm text-destructive">
                  {refusal in COPY_CODES
                    ? line(refusal)
                    : t("settings.migration.failed")}
                </p>
              )}
              <div
                role="group"
                className="flex w-full flex-col gap-2 sm:flex-row"
                onFocus={() => {
                  focused.current = true;
                }}
                onBlur={(event) => {
                  // A button that is removed leaves no element behind, so only a move to another one counts.
                  if (event.relatedTarget)
                    focused.current = event.currentTarget.contains(
                      event.relatedTarget,
                    );
                }}
              >
                <Button
                  className="w-full sm:w-fit"
                  // One start at a time: a second one while the first is on its way is refused as running elsewhere.
                  disabled={start.isPending}
                  loading={start.isPending && !start.variables}
                  onClick={() => {
                    // A new copy leaves the last choice, and how it went, behind.
                    decide.reset();
                    start.mutate(false);
                  }}
                  ignoreTitleCase
                >
                  {/* A test run copied nothing, so the copy after it is still the first. */}
                  {run && !run.dry_run
                    ? t("settings.migration.copy.again")
                    : t(`settings.migration.step.${STEP_SLUGS[step]}.title`)}
                </Button>
                {/* A test run takes the copy's place in the record, so a done step offers none. */}
                {testRun && state.state !== "done" && (
                  <Button
                    variant="outline"
                    className="w-full sm:w-fit"
                    disabled={start.isPending}
                    loading={start.isPending && start.variables}
                    onClick={() => {
                      decide.reset();
                      start.mutate(true);
                    }}
                    ignoreTitleCase
                  >
                    {t("settings.migration.copy.testRun")}
                  </Button>
                )}
              </div>
            </>
          ) : (
            <p
              ref={gate}
              role="status"
              tabIndex={-1}
              className="text-sm outline-none"
            >
              {t("settings.migration.notStarted")}
            </p>
          )}
        </>
      )}
    </div>
  );
}

/**
 * One decision the server offers about a copy: ticked while the server holds it as made, and unticked to take it back.
 * One that names an item accepts it as it was left. One that names none is an option the next copy takes.
 */
function Decision({
  step,
  decision: { kind, subject, run_id, made },
  name,
  decide,
}: {
  step: CopyStepId;
  decision: CopyDecision;
  /** Names the item for a screen reader, since every row has the same label. */
  name?: string;
  decide: ReturnType<typeof useDecideMutation>;
}) {
  const { t, i18n } = useTranslation();
  const id = useId();
  // A decision this page has no words for is not one it can ask the admin to make.
  if (!DECISIONS[kind]) return null;
  const label = t(`settings.migration.${DECISIONS[kind]}`);
  // The last choice was this one, and it did not go through. One for a list that was replaced gets the step's own line.
  const failed =
    decide.isError &&
    !replaced(decide.error) &&
    decide.variables.kind === kind &&
    decide.variables.subject === subject;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        {/* aria-disabled, since native disabled would drop the keyboard user's focus to <body>. */}
        <Checkbox
          id={id}
          checked={Boolean(made)}
          aria-disabled={decide.isPending}
          aria-label={name && `${label}, ${name}`}
          className="aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
          onCheckedChange={(value) => {
            if (!decide.isPending)
              decide.mutate({
                step,
                kind,
                subject,
                run_id,
                made: value === true,
              });
          }}
        />
        <Label htmlFor={id} className="text-sm font-normal">
          {label}
        </Label>
      </div>
      {made && (
        <div className="text-xs text-muted-foreground">
          <p>
            {t("settings.migration.check.acceptedBy", {
              user: made.by,
              time: formatTime(made.at, i18n.language),
            })}
          </p>
          {subject === null && <p>{t("settings.migration.copy.applyNext")}</p>}
        </div>
      )}
      {failed && (
        <p role="alert" className="text-xs text-destructive">
          {t("settings.migration.failed")}
        </p>
      )}
    </div>
  );
}

/** Whether the server refused a choice because the run it named is no longer the one on record. */
const replaced = (error: AxiosError<{ detail?: MigrationError }> | null) =>
  error?.response?.data?.detail?.code === "report_changed";

/**
 * The last progress line of a run that is on. A run belongs to no page, so this one follows it from
 * the last line it saw: after a reload that is the first, and after a dropped connection the one it had got to.
 */
function useProgress(step: CopyStepId, run?: MigrationCopyRun) {
  const client = useQueryClient();
  const [progress, setProgress] = useState<CopyEvent>();
  const live = run?.status === "running" ? run.run_id : undefined;
  useEffect(() => {
    if (!live) return;
    setProgress(undefined);
    const controller = new AbortController();
    (async () => {
      let seq = 0;
      let over = false;
      while (!over && !controller.signal.aborted) {
        const refused = await followCopy({
          step,
          runId: live,
          after: seq,
          controller,
          onEvent: (event) => {
            seq = event.seq;
            if (event.event === "progress") setProgress(event);
            over ||= event.event === "end";
          },
        });
        // A run the server no longer has was started again from somewhere else.
        over ||= refused?.status === 404;
        if (!over)
          await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
      }
      // The server writes down how a run ended the next time the record is read.
      if (!controller.signal.aborted)
        client.invalidateQueries({ queryKey: migrationKeys.all });
    })();
    return () => controller.abort();
  }, [step, live, client]);
  return progress;
}
