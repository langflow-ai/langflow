import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { BoundFlowDependency } from "@/pages/MainPage/entities";

export function FlowBindingDependencies({
  dependencies = [],
  reviewed,
  onOpen,
  title,
}: {
  dependencies?: BoundFlowDependency[];
  reviewed?: BoundFlowDependency[];
  onOpen?: () => void;
  title?: string;
}) {
  const { t } = useTranslation();
  const records = [
    ...dependencies,
    ...(reviewed ?? []).filter(
      (item) =>
        !dependencies.some((current) => current.flow_id === item.flow_id),
    ),
  ];
  if (!records.length) return null;
  return (
    <details className="rounded-md border border-border p-3 text-xs">
      <summary className="cursor-pointer font-medium">
        {title ?? t("toolPacks.nestedDependencies")} · {records.length}
      </summary>
      <ul className="mt-3 space-y-3">
        {records.map((item) => {
          const previous = reviewed?.find(
            (record) => record.flow_id === item.flow_id,
          );
          const current = dependencies.find(
            (record) => record.flow_id === item.flow_id,
          );
          const state = !reviewed
            ? undefined
            : !current
              ? "removed"
              : !previous
                ? "added"
                : previous.revision !== current.revision ||
                    previous.name !== current.name ||
                    (previous.description ?? "") !== (current.description ?? "")
                  ? "updated"
                  : undefined;
          return (
            <li key={item.flow_id} className="space-y-1 break-words">
              <div className="flex items-start justify-between gap-2">
                <Link
                  className="underline underline-offset-4"
                  to={`/flow/${encodeURIComponent(item.flow_id)}`}
                  onClick={onOpen}
                >
                  {item.name}
                </Link>
                {state && <span>{t(`toolPacks.${state}`)}</span>}
              </div>
              {item.description && (
                <p className="text-muted-foreground">{item.description}</p>
              )}
              <p className="text-muted-foreground">
                {t("toolPacks.flowRevision")}:{" "}
                <code title={item.revision}>{item.revision.slice(0, 12)}</code>
              </p>
              {previous && previous.revision !== item.revision && (
                <p className="text-muted-foreground">
                  <code title={previous.revision}>
                    {previous.revision.slice(0, 12)}
                  </code>{" "}
                  → <code>{item.revision.slice(0, 12)}</code>
                </p>
              )}
              {item.version_id && (
                <p className="text-muted-foreground">
                  {t("toolPacks.snapshot")}: <code>{item.version_id}</code>
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
