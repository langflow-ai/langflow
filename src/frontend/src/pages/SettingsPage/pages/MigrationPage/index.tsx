import type { AxiosError } from "axios";
import { Fragment, type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import { Separator } from "@/components/ui/separator";
import {
  type MigrationError,
  type MigrationState,
  type MigrationStepState,
  useMigrationQuery,
} from "@/controllers/API/queries/migration";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import { downloadJson } from "@/pages/FlowPage/components/TraceComponent/traceViewHelpers";
import useAuthStore from "@/stores/authStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import { BackupStep } from "./BackupStep";
import { CheckStep } from "./CheckStep";
import { formatTime, PARTS } from "./catalog";
import { DestinationsStep } from "./DestinationsStep";
import { PausedBanner, PauseStep, Recovery } from "./PauseStep";
import { SecretKeyStep } from "./SecretKeyStep";

const MARKER_ICONS: Partial<Record<MigrationStepState["state"], string>> = {
  locked: "Lock",
  skipped: "Minus",
  blocked: "CircleAlert",
  done: "Check",
};

// Until the server lists a step, it waits for the ones before it.
const NOT_LISTED: Omit<MigrationStepState, "id"> = {
  state: "locked",
  reason: "earlier_step",
};

export default function MigrationPage() {
  const { t } = useTranslation();
  const isSuperuser = Boolean(
    useAuthStore((state) => state.userData)?.is_superuser,
  );
  // Undefined until the server's flags arrive, which is after the first render when the page is opened by its address.
  const enabled = useUtilityStore(
    (state) => state.featureFlags.instance_migration,
  );
  const {
    data: migration,
    error,
    isLoading,
    refetch,
  } = useMigrationQuery(enabled === true && isSuperuser);
  const response = (error as AxiosError<{ detail?: MigrationError }> | null)
    ?.response;
  if (enabled === undefined)
    return <Loading aria-label={t("common.loading")} />;
  if (!enabled) return <CustomNavigate replace to="/settings" />;

  let body: ReactNode = null;
  if (!isSuperuser || response?.status === 403) {
    body = (
      <p className="text-sm text-muted-foreground">
        {t("settings.migration.superuserOnly")}
      </p>
    );
  } else if (migration) {
    // A failed refetch keeps the data, and unmounting here would stop a running check.
    body = <Migration migration={migration} />;
  } else if (isLoading) {
    body = <Loading aria-label={t("common.loading")} />;
  } else if (response?.data?.detail?.code === "record_unreadable") {
    body = (
      <Alert variant="destructive">
        <AlertDescription>
          {t("settings.migration.recordUnreadable", {
            path: response.data.detail.path,
          })}
        </AlertDescription>
      </Alert>
    );
  } else if (error) {
    body = (
      <Alert variant="destructive">
        <AlertDescription className="flex flex-col items-start gap-2">
          {t("settings.migration.loadError")}
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetch()}
            ignoreTitleCase
          >
            {t("common.retry")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex w-full flex-col gap-6 pb-8">
      <div className="flex flex-col">
        <h2
          className="flex items-center text-lg font-semibold tracking-tight"
          data-testid="settings_menu_header"
        >
          {t("settings.migration.title")}
          <ForwardedIconComponent
            name="ArrowRightLeft"
            className="ml-2 h-5 w-5 text-primary"
          />
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("settings.migration.description")}
        </p>
      </div>
      <div className="flex max-w-3xl flex-col gap-6">{body}</div>
    </div>
  );
}

function Migration({ migration }: { migration: MigrationState }) {
  const { t, i18n } = useTranslation();
  const { instance } = migration;
  const stateOf = (id: MigrationStepState["id"]) =>
    migration.steps?.find((step) => step.id === id) ?? { id, ...NOT_LISTED };
  const { record } = migration;
  const run = record.steps.check_source;

  const facts = [
    {
      icon: "Tag",
      text: t("settings.migration.instance.version", {
        version: instance.version,
      }),
    },
    {
      icon: "Database",
      text:
        instance.database.type === "sqlite"
          ? t("settings.migration.instance.sqlite")
          : t("settings.migration.instance.postgres"),
    },
    {
      icon: "Library",
      text: instance.knowledge_bases.local
        ? t("settings.migration.instance.kbLocal")
        : t("settings.migration.instance.kbNone"),
    },
    {
      icon: "FileText",
      text:
        instance.files.storage === "s3"
          ? t("settings.migration.instance.filesS3")
          : instance.files.local
            ? t("settings.migration.instance.filesLocal")
            : t("settings.migration.instance.filesNone"),
    },
  ];

  let number = 0;
  return (
    <>
      <PausedBanner migration={migration} />
      <section className="overflow-hidden rounded-lg border">
        <div className="flex flex-col gap-3 p-4">
          <h3 className="text-sm font-medium">
            {t("settings.migration.instance.title")}
          </h3>
          <ul
            className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2"
            data-testid="migration-instance"
          >
            {facts.map((fact) => (
              <li key={fact.icon} className="flex items-center gap-2 text-sm">
                <ForwardedIconComponent
                  name={fact.icon}
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                {fact.text}
              </li>
            ))}
          </ul>
        </div>
        <p
          role="note"
          className="flex items-start gap-2 border-t bg-muted/40 px-4 py-3 text-sm text-muted-foreground"
        >
          <ForwardedIconComponent
            name="Info"
            className="mt-0.5 h-4 w-4 shrink-0"
            aria-hidden="true"
          />
          {t("settings.migration.oneWay")}
        </p>
      </section>

      {PARTS.map((part, index) => (
        <Fragment key={part.slug}>
          {index === PARTS.length - 1 ? (
            <div className="flex flex-col gap-1 border-t-2 border-destructive pt-2">
              <span className="text-sm font-semibold text-destructive">
                {t("settings.migration.oneWay.label")}
              </span>
              <span className="text-sm text-muted-foreground">
                {t("settings.migration.oneWay.text")}
              </span>
            </div>
          ) : (
            index > 0 && <Separator />
          )}
          <section className="flex flex-col gap-3">
            <div className="flex flex-col">
              <h3 className="text-base font-semibold">
                {t(`settings.migration.part.${part.slug}.title`)}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t(`settings.migration.part.${part.slug}.subtitle`)}
              </p>
            </div>
            <ol className="flex flex-col gap-3" start={number + 1}>
              {part.steps.map((step) => {
                number += 1;
                const state = stateOf(step.id);
                const isCheck = step.id === "check_source";
                let summary: ReactNode = t(
                  `settings.migration.step.${step.slug}.purpose`,
                );
                if (state.state === "skipped") {
                  summary = t(`settings.migration.skip.${step.slug}`);
                } else if (isCheck && state.state === "blocked") {
                  summary = t("settings.migration.check.blocking", {
                    count: migration.blocking_findings.length,
                  });
                } else if (isCheck && state.state === "done") {
                  summary = t("settings.migration.check.doneSummary", {
                    time: formatTime(run?.finished_at, i18n.language),
                  });
                } else if (
                  step.id === "connect_target" &&
                  state.state === "done"
                ) {
                  const saved = record.destinations;
                  summary = [
                    saved?.database &&
                      t("settings.migration.dest.done.db", {
                        location: saved.database.location,
                      }),
                    saved?.vectors?.kind === "pgvector" &&
                      t("settings.migration.dest.done.kb.pgvector"),
                    saved?.files &&
                      t("settings.migration.dest.done.files", {
                        bucket: saved.files.bucket,
                      }),
                  ]
                    .filter(Boolean)
                    .join(" · ");
                } else if (step.id === "secret_key" && state.state === "done") {
                  summary = t("settings.migration.key.done", {
                    time: formatTime(
                      record.secret_key?.verified_at,
                      i18n.language,
                    ),
                    user: record.secret_key?.verified_by,
                  });
                } else if (step.id === "pause" && state.state === "done") {
                  summary = t("settings.migration.pause.done", {
                    time: formatTime(record.pause?.frozen_at, i18n.language),
                    user: record.pause?.frozen_by,
                  });
                } else if (step.id === "backup" && state.state === "done") {
                  summary = t("settings.migration.backup.done", {
                    time: formatTime(
                      record.backup?.confirmed_at,
                      i18n.language,
                    ),
                    location: record.backup?.location,
                  });
                }
                // A step the admin has reached, and that this server can do.
                const live =
                  state.reason !== "not_available" &&
                  ["current", "blocked", "done"].includes(state.state);
                // Once done, a step with nothing left to change says all there is to say in its row.
                const unfinished = live && state.state !== "done";
                let body: ReactNode = null;
                if (isCheck) {
                  body = <CheckStep migration={migration} />;
                } else if (live && step.id === "connect_target") {
                  body = (
                    <DestinationsStep migration={migration} state={state} />
                  );
                } else if (unfinished && step.id === "secret_key") {
                  body = <SecretKeyStep migration={migration} state={state} />;
                } else if (unfinished && step.id === "pause") {
                  body = <PauseStep migration={migration} state={state} />;
                } else if (unfinished && step.id === "backup") {
                  body = <BackupStep migration={migration} />;
                }
                return (
                  <StepItem
                    key={step.id}
                    number={number}
                    title={t(`settings.migration.step.${step.slug}.title`)}
                    summary={summary}
                    state={state}
                    // The pause waits on the same run while it is checked again.
                    running={
                      run?.status === "running" &&
                      (isCheck || state.reason === "recheck_pending")
                    }
                    expandable={Boolean(body) && state.state === "done"}
                  >
                    {body}
                  </StepItem>
                );
              })}
            </ol>
          </section>
        </Fragment>
      ))}

      {stateOf("pause").reason !== "not_available" && (
        <Recovery migration={migration} />
      )}
      <Button
        variant="link"
        className="h-auto w-fit whitespace-normal px-0 text-left"
        onClick={() => downloadRecord(migration)}
        ignoreTitleCase
      >
        {t("settings.migration.record.download")}
      </Button>
    </>
  );
}

function StepItem({
  number,
  title,
  summary,
  state,
  running,
  expandable,
  children,
}: {
  number: number;
  title: string;
  summary: ReactNode;
  state: MigrationStepState;
  running: boolean;
  /** A done step the admin can open again, such as the check. */
  expandable: boolean;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const frontier = state.state === "current" || state.state === "blocked";
  // The step being worked on stays open once it's done, so the admin keeps its results and their place.
  const [open, setOpen] = useState(frontier);
  useEffect(() => {
    if (frontier) setOpen(true);
  }, [frontier]);
  const locked = state.state === "locked";
  const bodyId = `migration-step-${state.id}-body`;
  // The admin has reached this step, and either the server or this page can't do it yet.
  const comingSoon = frontier && !children;
  // When the step before this one finishes, keyboard and screen reader users land on what to do next.
  const heading = useRef<HTMLHeadingElement>(null);
  const wasLocked = useRef(locked);
  useEffect(() => {
    if (wasLocked.current && frontier && !comingSoon) heading.current?.focus();
    wasLocked.current = locked;
  }, [locked, frontier, comingSoon]);
  return (
    <li
      aria-current={frontier ? "step" : undefined}
      className="flex flex-col gap-3"
      data-testid={`migration-step-${state.id}`}
    >
      <div className="flex items-start gap-3">
        <Marker number={number} state={state.state} running={running} />
        <div className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h4
            ref={heading}
            tabIndex={-1}
            className={cn(
              "text-sm font-medium",
              locked && "text-muted-foreground",
            )}
          >
            {expandable && !frontier ? (
              <button
                type="button"
                className="flex items-center gap-1 text-left hover:underline"
                aria-expanded={open}
                aria-controls={bodyId}
                onClick={() => setOpen(!open)}
              >
                {title}
                <ForwardedIconComponent
                  name={open ? "ChevronUp" : "ChevronDown"}
                  className="h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
              </button>
            ) : (
              title
            )}
          </h4>
          {/* A summary can hold an address with nowhere to break, which has to fit a phone. */}
          <span className="flex items-center gap-2 text-sm text-muted-foreground [overflow-wrap:anywhere]">
            {summary}
            {locked && (
              <span className="sr-only">
                {t("settings.migration.notStarted")}
              </span>
            )}
            {comingSoon && (
              <Badge
                variant="secondaryStatic"
                size="sm"
                className="shrink-0 whitespace-nowrap"
              >
                {t("settings.migration.comingSoon")}
              </Badge>
            )}
          </span>
        </div>
      </div>
      {/* Hidden, never unmounted, so collapsing the check doesn't stop a run. */}
      {children && (
        <div
          id={bodyId}
          className="ml-9"
          hidden={!(open && (frontier || expandable))}
        >
          {children}
        </div>
      )}
    </li>
  );
}

function Marker({
  number,
  state,
  running,
}: {
  number: number;
  state: MigrationStepState["state"];
  running: boolean;
}) {
  const icon = running ? "Loader2" : MARKER_ICONS[state];
  return (
    <span
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs tabular-nums",
        state === "current" && !running
          ? "bg-primary text-primary-foreground"
          : "border text-muted-foreground",
        state === "blocked" &&
          !running &&
          "border-destructive text-destructive",
        state === "done" && "text-accent-emerald-foreground",
      )}
    >
      {icon ? (
        <ForwardedIconComponent
          name={icon}
          className={cn("h-4 w-4", running && "motion-safe:animate-spin")}
        />
      ) : (
        number
      )}
    </span>
  );
}

/** Saves what the page knows, for support. The record never holds a secret. */
function downloadRecord(migration: MigrationState) {
  const day = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  downloadJson(`langflow-migration-${day}.json`, migration);
}
