import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  type ToolDependencyUse,
  useProjectToolPack,
} from "@/controllers/API/queries/folders/use-project-tool-pack";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { packProjectPath } from "../tool-packs";

export function ReportDependencies({
  uses,
  harnessId,
  onOpen,
}: {
  uses: ToolDependencyUse[];
  harnessId: string;
  onOpen?: () => void;
}) {
  const { t } = useTranslation();
  const groups = new Map<string, ToolDependencyUse[]>();
  for (const use of uses) {
    const { reference, tool, version_id } = use.binding;
    const key = JSON.stringify([
      reference.project_id,
      reference.revision,
      tool.flow_id,
      tool.revision,
      version_id,
    ]);
    groups.set(key, [...(groups.get(key) ?? []), use]);
  }
  if (!uses.length) return null;
  return (
    <section
      className="mt-8 space-y-4 border-t border-border pt-4"
      aria-label={t("toolPacks.usedTitle")}
    >
      <div>
        <h3 className="text-sm font-semibold">{t("toolPacks.usedTitle")}</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {t("toolPacks.usedHelp")}
        </p>
      </div>
      {[...groups].map(([key, calls]) => (
        <UsedTool
          key={key}
          uses={calls}
          harnessId={harnessId}
          onOpen={onOpen}
        />
      ))}
    </section>
  );
}

function UsedTool({
  uses,
  harnessId,
  onOpen,
}: {
  uses: ToolDependencyUse[];
  harnessId: string;
  onOpen?: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const { reference, tool, version_id } = uses[0].binding;
  const current = useProjectToolPack({ projectId: reference.project_id });
  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <p className="break-words text-sm font-medium">{tool.name}</p>
      <p className="text-xs text-muted-foreground">
        {t("toolPacks.callCount", { count: uses.length })}
      </p>
      <p className="break-words text-xs">
        {current.data?.name ?? reference.project_id}
      </p>
      <p className="text-xs text-muted-foreground">
        {t(
          current.isError
            ? "toolPacks.currentUnavailable"
            : !current.data
              ? "toolPacks.loading"
              : current.data.reference.revision !== reference.revision
                ? "toolPacks.changedSinceRun"
                : "toolPacks.current",
        )}
      </p>
      <details className="text-xs">
        <summary className="cursor-pointer font-medium">
          {t("toolPacks.recordedRevisions")}
        </summary>
        <dl className="mt-3 space-y-2">
          {[
            [t("toolPacks.reviewedRevision"), reference.revision],
            [t("toolPacks.flowRevision"), tool.revision],
            [t("toolPacks.snapshot"), version_id],
          ].map(([label, revision]) => (
            <div key={label}>
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="break-all font-mono">{revision}</dd>
            </div>
          ))}
        </dl>
        <ul className="mt-3 space-y-1 break-all font-mono text-muted-foreground">
          {uses.map((use) => (
            <li key={use.tool_call_id}>
              {use.tool_name} · {use.tool_call_id}
            </li>
          ))}
        </ul>
      </details>
      <Button
        variant="outline"
        size="sm"
        disabled={!current.data || current.isError}
        onClick={() => {
          onOpen?.();
          navigate(packProjectPath(reference.project_id, harnessId));
        }}
      >
        {t("toolPacks.openPack")}
      </Button>
      {current.isError && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => void current.refetch()}
        >
          {t("toolPacks.retry")}
        </Button>
      )}
    </div>
  );
}
