import type { UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import type { ToolPackManifest } from "@/controllers/API/queries/folders/use-project-tool-pack";
import { UseRequestProcessor } from "@/controllers/API/services/request-processor";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import type { CapabilityReference, SkillPackManifest } from "../skills";

type Props = {
  kind: "skill-pack" | "tool-pack";
  value: CapabilityReference[];
  disabled?: boolean;
  projectId: string;
  onOpen?: () => void;
  onChange: (next: CapabilityReference[]) => void;
};

export function CapabilityPackPicker({
  kind,
  value,
  disabled,
  projectId,
  onOpen,
  onChange,
}: Props) {
  const { t } = useTranslation();
  const folders = useGetFoldersQuery();
  const [reviewing, setReviewing] = useState<string>();
  const [selected, setSelected] = useState("");
  const choices = (folders.data ?? []).filter(
    (folder) =>
      folder.project_type === kind &&
      !value.some((ref) => ref.project_id === folder.id),
  );
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {t(
          kind === "skill-pack" ? "skills.activationHelp" : "skills.scopeHelp",
        )}
      </p>
      {value.map((reference) => (
        <div
          className="flex items-center justify-between gap-3 rounded-md border p-3"
          key={reference.project_id}
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {folders.data?.find(
                (folder) => folder.id === reference.project_id,
              )?.name ?? t("skills.unavailablePack")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("skills.reviewedRevision", {
                revision: reference.revision.slice(0, 8),
              })}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={disabled}
              onClick={() => setReviewing(reference.project_id)}
            >
              {t("skills.review")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={disabled}
              onClick={() =>
                onChange(
                  value.filter(
                    (ref) => ref.project_id !== reference.project_id,
                  ),
                )
              }
            >
              {t("skills.remove")}
            </Button>
          </div>
        </div>
      ))}
      {folders.isError ? (
        <p role="alert">
          {t("skills.loadError")}{" "}
          <Button variant="link" onClick={() => void folders.refetch()}>
            {t("skills.retry")}
          </Button>
        </p>
      ) : (
        <div className="flex gap-2">
          <select
            className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-sm"
            aria-label={t(
              kind === "skill-pack"
                ? "skills.chooseSkillPack"
                : "skills.chooseToolPack",
            )}
            value={selected}
            disabled={disabled || folders.isLoading}
            onChange={(event) => setSelected(event.target.value)}
          >
            <option value="">
              {t(
                kind === "skill-pack"
                  ? "skills.chooseSkillPack"
                  : "skills.chooseToolPack",
              )}
            </option>
            {choices.map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.name}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            size="sm"
            disabled={
              disabled || !choices.some((folder) => folder.id === selected)
            }
            onClick={() => setReviewing(selected)}
          >
            {t("skills.review")}
          </Button>
        </div>
      )}
      {!folders.isLoading &&
        !folders.isError &&
        !choices.length &&
        !value.length && (
          <p className="text-xs text-muted-foreground">
            {t(
              kind === "skill-pack"
                ? "skills.createPackHelp"
                : "skills.createToolsHelp",
            )}
          </p>
        )}
      <Dialog
        open={!!reviewing}
        onOpenChange={(open) => {
          if (!open) setReviewing(undefined);
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogTitle>{t("skills.reviewTitle")}</DialogTitle>
          <DialogDescription>{t("skills.reviewHelp")}</DialogDescription>
          {reviewing && (
            <Review
              key={reviewing}
              id={reviewing}
              kind={kind}
              previous={value.find((ref) => ref.project_id === reviewing)}
              projectId={projectId}
              onOpen={onOpen}
              disabled={disabled}
              onAccept={(ref) => {
                onChange([
                  ...value.filter((item) => item.project_id !== ref.project_id),
                  ref,
                ]);
                setReviewing(undefined);
                setSelected("");
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Review({
  id,
  kind,
  previous,
  projectId,
  disabled,
  onOpen,
  onAccept,
}: {
  id: string;
  kind: Props["kind"];
  previous?: CapabilityReference;
  projectId: string;
  disabled?: boolean;
  onOpen?: () => void;
  onAccept: (ref: CapabilityReference) => void;
}) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const { query } = UseRequestProcessor();
  const result: UseQueryResult<SkillPackManifest | ToolPackManifest> = query(
    ["capabilityPack", kind, id],
    async ({ signal }) =>
      (
        await api.get(
          `${getURL("PROJECTS")}/${encodeURIComponent(id)}/${kind}`,
          { signal },
        )
      ).data,
    { retry: false, staleTime: 0 },
  );
  return (
    <div className="space-y-4">
      {result.isLoading ? (
        <p role="status">{t("skills.loading")}</p>
      ) : result.isError ? (
        <p role="alert">
          {t("skills.loadError")}{" "}
          <Button variant="link" onClick={() => void result.refetch()}>
            {t("skills.retry")}
          </Button>
        </p>
      ) : (
        result.data && (
          <>
            <h3 className="font-semibold">{result.data.name}</h3>
            {previous &&
              previous.revision !== result.data.reference.revision && (
                <p role="status" className="text-sm text-warning">
                  {t("skills.changed")}
                </p>
              )}
            {"skills" in result.data
              ? result.data.skills.map((skill) => (
                  <section
                    key={skill.name}
                    className="space-y-2 rounded-md border p-4"
                  >
                    <h4 className="font-medium">{skill.name}</h4>
                    <p className="text-sm text-muted-foreground">
                      {skill.description}
                    </p>
                    <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap font-sans text-sm">
                      {skill.instructions}
                    </pre>
                    <p className="text-xs text-muted-foreground">
                      {t("skills.toolPackCount", {
                        count: skill.tool_packs.length,
                      })}
                    </p>
                  </section>
                ))
              : result.data.tools.map((tool) => (
                  <section className="rounded-md border p-3" key={tool.flow_id}>
                    <p className="font-medium">{tool.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {tool.description}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("skills.reviewedRevision", {
                        revision: tool.revision.slice(0, 8),
                      })}
                    </p>
                  </section>
                ))}
            <Button
              disabled={disabled || result.isFetching}
              onClick={() => result.data && onAccept(result.data.reference)}
            >
              {t("skills.useRevision")}
            </Button>
          </>
        )
      )}
      <Button
        variant="outline"
        onClick={() => {
          onOpen?.();
          navigate(
            `/all/folder/${id}?tab=harness&fromHarness=${encodeURIComponent(projectId)}`,
          );
        }}
      >
        {t("skills.openPack")}
      </Button>
    </div>
  );
}
