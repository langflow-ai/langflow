import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import type {
  JobUsage,
  ReportFlow,
} from "@/controllers/API/queries/upgrade-reports";
import { reportReason, reportTime } from "./format";
import { usageReasonKey } from "./reasons";

export function Usage({ usage }: { usage?: JobUsage }) {
  const { t, i18n } = useTranslation();
  const unknown = t("settings.upgrade.unknown");
  if (!usage || usage.history === "unavailable")
    return <p>{t("settings.upgrade.historyUnavailable")}</p>;
  return (
    <div className="space-y-1">
      <p>
        {t("settings.upgrade.usageCounts", {
          runs:
            usage.runs === null
              ? unknown
              : new Intl.NumberFormat(i18n.language).format(usage.runs),
          errors:
            usage.errors === null
              ? unknown
              : new Intl.NumberFormat(i18n.language).format(usage.errors),
          last: reportTime(usage.last_run_at, i18n.language, unknown),
        })}
      </p>
      <p>
        {t("settings.upgrade.retainedPeriod", {
          start: reportTime(
            usage.coverage.oldest_retained_at,
            i18n.language,
            unknown,
          ),
          end: reportTime(
            usage.coverage.newest_retained_at,
            i18n.language,
            unknown,
          ),
        })}
      </p>
      <p>
        {t(
          usage.history === "no_retained_records"
            ? "settings.upgrade.noRetained"
            : "settings.upgrade.partialHistory",
        )}
      </p>
      {usage.coverage.retention_days !== null && (
        <p>
          {t("settings.upgrade.retention", {
            days: usage.coverage.retention_days,
          })}
        </p>
      )}
      <ul>
        {[
          ...new Set([
            ...(usage.coverage.retention_days === null
              ? ["settings.upgrade.retentionUnknown"]
              : []),
            ...usage.limitations
              .map(usageReasonKey)
              .filter((key): key is string => key !== null),
          ]),
        ].map((key) => (
          <li key={key}>{t(key)}</li>
        ))}
      </ul>
    </div>
  );
}

export default function FlowList({
  flows,
  selected,
  onSelect,
}: {
  flows: ReportFlow[];
  selected: Set<string>;
  onSelect: (id: string, checked: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [unknownEdit, setUnknownEdit] = useState(false);
  const [page, setPage] = useState(0);
  const unknown = t("settings.upgrade.unknown");
  const filtered = flows.filter((flow) => {
    const matchesStatus =
      status === "all" ||
      flow.status === status ||
      flow.nodes.some((node) => node.status === status);
    return (
      matchesStatus &&
      (!unknownEdit || !flow.last_edited_at) &&
      [
        flow.name,
        flow.id,
        flow.owner?.username,
        flow.project?.name,
        ...(flow.labels ?? []),
      ]
        .join(" ")
        .toLocaleLowerCase(i18n.language)
        .includes(search.toLocaleLowerCase(i18n.language))
    );
  });
  const currentPage = Math.min(
    page,
    Math.max(0, Math.ceil(filtered.length / 20) - 1),
  );
  return (
    <section aria-labelledby="upgrade-flows-title" className="space-y-4">
      <h3 id="upgrade-flows-title" className="font-medium">
        {t("settings.upgrade.flows")}
      </h3>
      <div className="grid min-w-0 grid-cols-1 items-end gap-3 rounded-lg bg-muted/50 p-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <label className="flex min-w-0 flex-1 flex-col gap-1">
          {t("settings.upgrade.search")}
          <input
            className="rounded border border-control bg-background p-2"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          {t("settings.upgrade.status")}
          <select
            className="rounded border border-control bg-background p-2"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(0);
            }}
          >
            {["all", "ok", "warn", "fail", "could_not_verify"].map((value) => (
              <option key={value} value={value}>
                {t(`settings.upgrade.status.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            checked={unknownEdit}
            onChange={(event) => {
              setUnknownEdit(event.target.checked);
              setPage(0);
            }}
          />
          {t("settings.upgrade.unknownEditOnly")}
        </label>
      </div>

      {filtered.slice(currentPage * 20, currentPage * 20 + 20).map((flow) => (
        <article
          key={`${flow.kind}-${flow.id}`}
          className="min-w-0 rounded border p-3 [overflow-wrap:anywhere]"
        >
          <div className="mb-2 flex items-start gap-2">
            {flow.kind === "flow" && (
              <input
                type="checkbox"
                aria-label={t("settings.upgrade.selectFlow", {
                  name: flow.name ?? flow.id,
                })}
                checked={selected.has(flow.id)}
                disabled={!selected.has(flow.id) && selected.size >= 100}
                onChange={(event) => onSelect(flow.id, event.target.checked)}
              />
            )}
            <h4 className="min-w-0 flex-1 font-medium">
              {flow.name ?? unknown}
            </h4>
            <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium">
              {t(`settings.upgrade.status.${flow.status}`)}
            </span>
          </div>
          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">
                {t("settings.upgrade.owner")}
              </dt>
              <dd>{flow.owner?.username ?? flow.owner?.id ?? unknown}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                {t("settings.upgrade.project")}
              </dt>
              <dd>{flow.project?.name ?? unknown}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                {t("settings.upgrade.lastEdited")}
              </dt>
              <dd>{reportTime(flow.last_edited_at, i18n.language, unknown)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                {t("settings.upgrade.version")}
              </dt>
              <dd>{flow.version_number ?? unknown}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                {t("settings.upgrade.kind")}
              </dt>
              <dd>{t(`settings.upgrade.kind.${flow.kind}`)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                {t("settings.upgrade.labels")}
              </dt>
              <dd>{flow.labels?.join(", ") || unknown}</dd>
            </div>
          </dl>
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer">
              {t("settings.upgrade.flowDetails")}
            </summary>
            {flow.error && <p>{flow.error}</p>}
            <ul className="mt-2 space-y-2">
              {flow.nodes.map((node) => (
                <li key={`${node.group_path.join("/")}/${node.id}`}>
                  <p>
                    {node.display_name} ·{" "}
                    {t(`settings.upgrade.nodeStatus.${node.status}`, {
                      defaultValue: node.status,
                    })}
                  </p>
                  {node.reasons.map((reason, index) => (
                    <p key={`${reason.code}-${index}`}>
                      {reportReason(reason)}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
            <p className="mt-2">
              {t("settings.upgrade.flowId", { id: flow.flow_id ?? flow.id })}
            </p>
            <p>
              {t("settings.upgrade.deployments", {
                deployments: flow.used_by
                  ? ["deployments", "triggers"]
                      .flatMap((kind) => {
                        const ids = flow.used_by?.[kind];
                        return ids?.length
                          ? [
                              t(`settings.upgrade.usedBy.${kind}`, {
                                ids: ids.join(", "),
                              }),
                            ]
                          : [];
                      })
                      .join(" · ") || t("settings.upgrade.none")
                  : unknown,
              })}
            </p>
            <h5 className="mt-2 font-medium">
              {t("settings.upgrade.editorUsage")}
            </h5>
            <Usage usage={flow.usage?.editor} />
            <h5 className="mt-2 font-medium">
              {t("settings.upgrade.servingUsage")}
            </h5>
            <Usage usage={flow.usage?.serving} />
          </details>
        </article>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        <p role="status" className="mr-auto text-sm text-muted-foreground">
          {filtered.length
            ? t("settings.upgrade.rowRange", {
                first: currentPage * 20 + 1,
                last: Math.min((currentPage + 1) * 20, filtered.length),
                total: filtered.length,
              })
            : t("settings.upgrade.matching", { count: 0 })}
        </p>
        <Button
          variant="outline"
          disabled={currentPage === 0}
          onClick={() => setPage(currentPage - 1)}
          ignoreTitleCase
        >
          {t("settings.upgrade.previous")}
        </Button>
        <Button
          variant="outline"
          disabled={(currentPage + 1) * 20 >= filtered.length}
          onClick={() => setPage(currentPage + 1)}
          ignoreTitleCase
        >
          {t("settings.upgrade.next")}
        </Button>
      </div>
    </section>
  );
}
