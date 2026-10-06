import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input, type InputProps } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type MigrationState,
  type MigrationStepState,
  type ProbeResult,
  useSaveDestinationsMutation,
} from "@/controllers/API/queries/migration";
import { destinationsRequest, formatTime, PROBES } from "./catalog";

/** The body of "Where your data goes": one section for each kind of data this instance keeps on its own server. */
export function DestinationsStep({
  migration,
  state,
}: {
  migration: MigrationState;
  state: MigrationStepState;
}) {
  const { t, i18n } = useTranslation();
  const save = useSaveDestinationsMutation();
  // A done step asks again when a destination changes, or after a restart dropped the passwords.
  const [editing, setEditing] = useState(false);
  const { instance } = migration;
  const saved = migration.record.destinations;
  // What the last test found: this page's own, or the one the record keeps while the step is refused.
  // A request that failed tested nothing, so the record's results are not shown as its outcome.
  const results =
    save.data?.results ??
    (state.state === "blocked" && !save.isError ? saved?.results : undefined);

  if (state.state === "done" && !editing) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm">
          {t("settings.migration.dest.done.saved", {
            time: formatTime(saved?.saved_at, i18n.language),
            user: saved?.saved_by,
          })}
        </p>
        <p className="text-sm text-muted-foreground">
          {t("settings.migration.dest.memoryNote")}
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            // The last test was of what is saved, and says nothing about what the admin enters next.
            save.reset();
            setEditing(true);
          }}
          ignoreTitleCase
        >
          {t("settings.migration.dest.change")}
        </Button>
      </div>
    );
  }

  const filesProbe = results?.files && !results.files.ok && results.files.code;
  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate(
          destinationsRequest(instance, new FormData(event.currentTarget)),
          { onSuccess: () => setEditing(false) },
        );
      }}
    >
      <p className="text-sm text-muted-foreground">
        {t("settings.migration.dest.body")}
      </p>
      <Section title={t("settings.migration.dest.db.title")}>
        {instance.database.type === "sqlite" ? (
          <Field
            name="database_url"
            label={t("settings.migration.dest.db.url")}
            help={t("settings.migration.dest.db.help")}
            type="password"
            required
            probe="migration-probe-database"
            invalid={results?.database?.ok === false}
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("settings.migration.dest.db.shared", {
              location: instance.database.location,
            })}
          </p>
        )}
        <Probe id="migration-probe-database" result={results?.database} />
      </Section>

      {instance.knowledge_bases.local && (
        <Section title={t("settings.migration.dest.kb.title")}>
          <p className="text-sm text-muted-foreground">
            {/* An instance on PostgreSQL copies them to the store its own server reads, which is no database of the new instance's. */}
            {instance.database.type === "sqlite"
              ? t("settings.migration.dest.kb.pgvector")
              : t("settings.migration.dest.kb.pgvectorOwn")}
          </p>
          <Probe id="migration-probe-vectors" result={results?.vectors} />
        </Section>
      )}

      {instance.files.local && (
        <Section title={t("settings.migration.dest.files.title")}>
          <Field
            name="bucket"
            label={t("settings.migration.dest.files.bucket")}
            defaultValue={saved?.files?.bucket}
            required
            probe="migration-probe-files"
            invalid={filesProbe === "bucket_missing"}
          />
          <Field
            name="prefix"
            label={t("settings.migration.dest.files.folder")}
            defaultValue={saved?.files?.prefix ?? "files"}
            required
          />
          <Field
            name="access_key_id"
            label={t("settings.migration.dest.files.keyId")}
            required
            probe="migration-probe-files"
            invalid={filesProbe === "bucket_denied"}
          />
          <Field
            name="secret_access_key"
            label={t("settings.migration.dest.files.key")}
            type="password"
            required
            probe="migration-probe-files"
            invalid={filesProbe === "bucket_denied"}
          />
          <Field
            name="endpoint_url"
            label={t("settings.migration.dest.files.endpoint")}
            help={t("settings.migration.dest.files.endpointHelp")}
            defaultValue={saved?.files?.endpoint_url ?? undefined}
            probe="migration-probe-files"
            invalid={filesProbe === "bucket_unreachable"}
          />
          <details>
            <summary className="cursor-pointer text-sm text-muted-foreground">
              {t("settings.migration.dest.files.more")}
            </summary>
            <div className="pt-2">
              <Field
                name="ca_bundle"
                label={t("settings.migration.dest.files.ca")}
              />
            </div>
          </details>
          <Probe id="migration-probe-files" result={results?.files} />
        </Section>
      )}

      <p className="text-xs text-muted-foreground">
        {t("settings.migration.dest.memoryNote")}
      </p>
      {save.isError && (
        <p role="alert" className="text-sm text-destructive">
          {t("settings.migration.failed")}
        </p>
      )}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          type="submit"
          className="w-full sm:w-fit"
          loading={save.isPending}
          ignoreTitleCase
        >
          {t("settings.migration.dest.action")}
        </Button>
        {editing && (
          <Button
            type="button"
            variant="outline"
            className="w-full sm:w-fit"
            onClick={() => setEditing(false)}
            ignoreTitleCase
          >
            {t("modal.cancelButton")}
          </Button>
        )}
      </div>
    </form>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h5 className="text-sm font-semibold">{title}</h5>
      {children}
    </section>
  );
}

function Field({
  name,
  label,
  help,
  probe,
  invalid,
  ...input
}: InputProps & {
  name: string;
  label: string;
  help?: string;
  /** The id of the line that says why the server refused this field. */
  probe?: string;
  invalid?: boolean;
}) {
  const id = `migration-destination-${name}`;
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        name={name}
        className="aria-[invalid=true]:border-destructive"
        spellCheck={false}
        aria-invalid={Boolean(invalid)}
        aria-describedby={
          [invalid && probe, help && `${id}-help`].filter(Boolean).join(" ") ||
          undefined
        }
        {...input}
      />
      {help && (
        <p id={`${id}-help`} className="text-xs text-muted-foreground">
          {help}
        </p>
      )}
    </div>
  );
}

/** What the server found for one destination, in words as well as colour. */
function Probe({ id, result }: { id: string; result?: ProbeResult }) {
  const { t } = useTranslation();
  if (!result) return null;
  if (result.ok) {
    return (
      <p id={id} className="text-sm text-accent-emerald-foreground">
        {t("settings.migration.probe.ok")}
      </p>
    );
  }
  const line = result.code && PROBES[result.code];
  // The server's own words for what it ran into, or its code when this page has no line for it.
  const words = result.reason ?? (line ? undefined : result.code);
  return (
    <div id={id} role="alert" className="break-words text-sm text-destructive">
      {line && <p>{t(`settings.migration.${line}`)}</p>}
      {words && (
        <p lang="en" className="text-xs">
          {words}
        </p>
      )}
    </div>
  );
}
