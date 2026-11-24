import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  type MigrationState,
  useAcceptDifferencesMutation,
  useStartCopyMutation,
  useStopCopyMutation,
} from "@/controllers/API/queries/migration";
import { Details } from "./CheckStep";
import { COPY_CODES, STEP_SLUGS, targetCheck } from "./catalog";

const STEP = "check_target";
// Why the server did not take the admin's word about the differences. The record it sends back says what to
// do, and this says it in words.
const ACCEPT_CODES: Record<string, string> = {
  not_checked: "checkTarget.checkFirst",
  differences: "checkTarget.readFirst",
  // Someone ran the check again after this page read it. The page then shows that one, with nothing ticked.
  report_changed: "checkTarget.readFirst",
  locked: "notStarted",
};

/**
 * The body of "Check the copy". The server runs the checks of the first step on the copied data and sets each
 * result beside this instance's. It runs before the new instance starts, so what is missing can still be
 * copied again. A copy that matches needs nothing more. The page shows what differs, and the admin goes on
 * with a difference only after saying that it is expected.
 */
export function CheckTargetStep({ migration }: { migration: MigrationState }) {
  const { t } = useTranslation();
  // The server sends this only while it counts: a check that read a copy made again since, or another
  // destination, is not in the record the page gets.
  const run = migration.record.steps.check_target;
  const start = useStartCopyMutation(STEP);
  const stop = useStopCopyMutation(STEP);
  const accept = useAcceptDifferencesMutation();
  const expectedId = useId();
  // The run whose differences the admin said are expected. Another run asks again.
  const [expectedRun, setExpectedRun] = useState<string>();
  // A refused start or stop is about the run it was shown beside. Once the record holds another run, or the
  // same one moved on, it no longer says anything true.
  const { reset: forgetStart } = start;
  const { reset: forgetStop } = stop;
  useEffect(() => {
    forgetStart();
    forgetStop();
  }, [run?.run_id, run?.status, forgetStart, forgetStop]);
  // A refused acceptance often comes with another record: the check ran again, or a copy was made again. Its
  // line is what explains the change, so it stays until the admin does what it asks.

  if (run?.status === "running") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="status" className="text-sm">
          {t("settings.migration.checkTarget.running")}
        </p>
        {stop.isError && (
          <p role="alert" className="text-sm text-destructive">
            {t("settings.migration.failed")}
          </p>
        )}
        <Button
          variant="outline"
          size="sm"
          // The record says that it stopped a moment after the server did. Until then a second press on the
          // same run has nothing to stop.
          loading={
            stop.isPending || (stop.isSuccess && stop.variables === run.run_id)
          }
          // It reads and changes nothing, so stopping it loses nothing and asks for no second word.
          onClick={() => run.run_id && stop.mutate(run.run_id)}
          ignoreTitleCase
        >
          {t("settings.migration.check.stop")}
        </Button>
      </div>
    );
  }

  const checks = run?.report?.checks ?? [];
  const differing = checks.filter((check) => !check.same);
  // When this server can't read the copied database, that is the only thing the check reports. Nothing was
  // compared then, so there is nothing the admin could call expected.
  const unreadable =
    checks.length === 1 &&
    checks[0].name === "schema" &&
    checks[0].there.status === "fail";
  const expected = Boolean(run?.run_id) && expectedRun === run?.run_id;
  // A request the server refused, or that never reached it, leaves the last result as it stands.
  const refusal = start.error?.response?.data?.detail?.code ?? "";
  const refused = accept.error?.response?.data?.detail?.code ?? "";
  const destinations = t(
    `settings.migration.step.${STEP_SLUGS.connect_target}.title`,
  );
  const line = (code: string) =>
    t(`settings.migration.${COPY_CODES[code] ?? "error.crashed"}`, {
      step: destinations,
    });

  return (
    <div className="flex flex-col items-start gap-4">
      <p className="text-sm text-muted-foreground">
        {t("settings.migration.checkTarget.body")}
      </p>
      {start.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {refusal in COPY_CODES
            ? line(refusal)
            : t("settings.migration.failed")}
        </p>
      ) : (
        run?.error && (
          <div className="flex w-full flex-col gap-1">
            <p role="alert" className="text-sm text-destructive">
              {line(run.error.code)}
            </p>
            {run.error.message && <Details text={run.error.message} />}
          </div>
        )
      )}
      {differing.length > 0 && (
        <div className="flex w-full flex-col gap-2">
          <p role="alert" className="text-sm text-destructive">
            {t("settings.migration.checkTarget.differs", {
              count: differing.length,
            })}
          </p>
          <ul className="flex flex-col gap-2">
            {differing.map((check) => {
              const known = targetCheck(check.name);
              return (
                <li
                  key={check.name}
                  className="flex flex-col gap-1 rounded-md border p-3 text-sm"
                  data-testid={`migration-difference-${check.name}`}
                >
                  <span className="font-medium">
                    {known ? (
                      t(`settings.migration.check.${known.slug}.title`)
                    ) : (
                      <span lang="en">{check.name}</span>
                    )}
                  </span>
                  <dl className="grid grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-[auto_1fr]">
                    <dt className="text-muted-foreground">
                      {t("settings.migration.checkTarget.here")}
                    </dt>
                    {/* The tool's own words, in English in every language. The page's own sentence is not. */}
                    <dd
                      lang={check.here ? "en" : undefined}
                      className="break-words"
                    >
                      {check.here?.summary ??
                        t("settings.migration.checkTarget.notChecked")}
                    </dd>
                    <dt className="text-muted-foreground">
                      {t("settings.migration.checkTarget.there")}
                    </dt>
                    <dd lang="en" className="break-words">
                      {check.there.summary}
                    </dd>
                  </dl>
                  {Boolean(check.there.problems?.length) && (
                    <Details text={(check.there.problems ?? []).join("\n")} />
                  )}
                </li>
              );
            })}
          </ul>
          <p className="text-xs text-muted-foreground">
            {unreadable
              ? t("settings.migration.checkTarget.unreadable", {
                  step: destinations,
                })
              : t("settings.migration.checkTarget.diffHint")}
          </p>
        </div>
      )}
      {differing.length > 0 && !unreadable && (
        <div className="flex items-center gap-2">
          <Checkbox
            id={expectedId}
            checked={expected}
            onCheckedChange={(value) => {
              accept.reset();
              setExpectedRun(value === true ? run?.run_id : undefined);
            }}
          />
          <Label
            id={`${expectedId}-label`}
            htmlFor={expectedId}
            className="text-sm font-normal"
          >
            {t("settings.migration.checkTarget.expected")}
          </Label>
        </div>
      )}
      {accept.isError && (
        <p role="alert" className="text-sm text-destructive">
          {t(`settings.migration.${ACCEPT_CODES[refused] ?? "failed"}`)}
        </p>
      )}
      <div className="flex w-full flex-col gap-2 sm:flex-row">
        <Button
          // With differences on the page, checking again comes after copying again, so it is the second choice
          // only once the admin said that they are expected.
          variant={expected ? "outline" : "default"}
          className="w-full sm:w-fit"
          loading={start.isPending}
          onClick={() => {
            accept.reset();
            start.mutate(false);
          }}
          ignoreTitleCase
        >
          {t(
            run
              ? "settings.migration.checkTarget.again"
              : "settings.migration.checkTarget.action",
          )}
        </Button>
        {differing.length > 0 && !unreadable && (
          <Button
            variant={expected ? "default" : "outline"}
            className="w-full sm:w-fit"
            loading={accept.isPending}
            disabled={!expected}
            // What the disabled button waits for is the sentence beside the box.
            aria-describedby={expected ? undefined : `${expectedId}-label`}
            onClick={() => run?.run_id && accept.mutate(run.run_id)}
            ignoreTitleCase
          >
            {t("settings.migration.checkTarget.accept")}
          </Button>
        )}
      </div>
    </div>
  );
}
