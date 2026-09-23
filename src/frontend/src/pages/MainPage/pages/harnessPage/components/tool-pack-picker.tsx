import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import {
  type ToolPackReference,
  useProjectToolPack,
} from "@/controllers/API/queries/folders/use-project-tool-pack";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import type { FlowType } from "@/types/flow";
import {
  appliedPackTools,
  exportChanges,
  packProjectPath,
} from "../tool-packs";
import { ProjectChoiceField } from "./project-choice-field";

type Props = {
  projectId: string;
  value: ToolPackReference[];
  saved: ToolPackReference[];
  agent?: FlowType;
  disabled?: boolean;
  onChange: (references: ToolPackReference[]) => void;
  onOpen: () => void;
};

export function ToolPackPicker({
  projectId,
  value,
  saved,
  agent,
  disabled,
  onChange,
  onOpen,
}: Props) {
  const { t } = useTranslation();
  const folders = useGetFoldersQuery();
  const [candidate, setCandidate] = useState("");
  const [reviewing, setReviewing] = useState<string>();
  const trigger = useRef<HTMLButtonElement>(null);
  const choices = (folders.data ?? []).filter(
    (project) =>
      project.project_type === "tool-pack" &&
      project.id !== projectId &&
      !value.some((reference) => reference.project_id === project.id),
  );
  const review = (id: string, button: HTMLButtonElement) => {
    trigger.current = button;
    setReviewing(id);
  };
  return (
    <div className="space-y-4" data-testid="tool-pack-picker">
      <p className="text-xs leading-relaxed text-muted-foreground">
        {t("toolPacks.description")}
      </p>
      <ul className="divide-y divide-border rounded-md border border-border empty:hidden">
        {value.map((reference) => (
          <PackRow
            key={reference.project_id}
            reference={reference}
            harnessId={projectId}
            name={
              folders.data?.find(
                (project) => project.id === reference.project_id,
              )?.name
            }
            pending={
              !saved.some(
                (item) =>
                  item.project_id === reference.project_id &&
                  item.revision === reference.revision,
              )
            }
            disabled={disabled}
            onOpen={onOpen}
            onReview={(button) => review(reference.project_id, button)}
            onRemove={() =>
              onChange(
                value.filter(
                  (item) => item.project_id !== reference.project_id,
                ),
              )
            }
          />
        ))}
      </ul>
      {folders.isError ? (
        <div role="alert" className="space-y-2 text-sm">
          <p>{t("toolPacks.listError")}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void folders.refetch()}
          >
            {t("toolPacks.retry")}
          </Button>
        </div>
      ) : folders.isLoading ? (
        <p role="status" className="text-sm text-muted-foreground">
          {t("toolPacks.loading")}
        </p>
      ) : choices.length ? (
        <div className="flex items-center gap-2">
          <ProjectChoiceField
            name="tool-pack-picker"
            label={t("toolPacks.choose")}
            placeholder={t("toolPacks.choose")}
            className="h-10 flex-1"
            value={
              choices.some((project) => project.id === candidate)
                ? candidate
                : ""
            }
            disabled={disabled || !agent}
            onChange={setCandidate}
            options={Object.fromEntries(
              choices.map((project) => [project.id, project.name]),
            )}
          />
          <Button
            className="h-10"
            variant="outline"
            disabled={
              disabled || !agent || !choices.some((p) => p.id === candidate)
            }
            onClick={(event) => review(candidate, event.currentTarget)}
          >
            {t("toolPacks.review")}
          </Button>
        </div>
      ) : !value.length ? (
        <p className="text-sm text-muted-foreground">{t("toolPacks.empty")}</p>
      ) : null}
      <Dialog
        open={!!reviewing}
        onOpenChange={(open) => {
          if (!open) setReviewing(undefined);
        }}
      >
        <DialogContent
          className="flex max-h-[85vh] max-w-2xl flex-col overflow-hidden"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            trigger.current?.focus();
          }}
        >
          <DialogTitle>{t("toolPacks.reviewTitle")}</DialogTitle>
          <DialogDescription>{t("toolPacks.reviewHelp")}</DialogDescription>
          {reviewing && (
            <PackReview
              key={reviewing}
              projectId={reviewing}
              harnessId={projectId}
              previous={saved.find((item) => item.project_id === reviewing)}
              agent={agent}
              disabled={disabled || !agent}
              onOpen={onOpen}
              onAccept={(reference) => {
                onChange(
                  value.some((item) => item.project_id === reference.project_id)
                    ? value.map((item) =>
                        item.project_id === reference.project_id
                          ? reference
                          : item,
                      )
                    : [...value, reference],
                );
                setReviewing(undefined);
                setCandidate("");
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PackRow({
  reference,
  name,
  harnessId,
  pending,
  disabled,
  onOpen,
  onReview,
  onRemove,
}: {
  reference: ToolPackReference;
  name?: string;
  harnessId: string;
  pending: boolean;
  disabled?: boolean;
  onOpen: () => void;
  onReview: (button: HTMLButtonElement) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const pack = useProjectToolPack({ projectId: reference.project_id });
  const changed = pack.data?.reference.revision !== reference.revision;
  const label = pack.data?.name ?? name ?? reference.project_id;
  return (
    <li className="space-y-2 p-3" aria-label={label}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="break-words text-sm font-medium">{label}</p>
          <p
            className={`text-xs ${pack.isError || (pack.data && changed) ? "text-destructive" : "text-muted-foreground"}`}
          >
            {t(
              pack.isError
                ? "toolPacks.unavailable"
                : pack.isLoading
                  ? "toolPacks.loading"
                  : changed
                    ? "toolPacks.changed"
                    : pending
                      ? "toolPacks.pending"
                      : "toolPacks.current",
            )}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          disabled={disabled}
          aria-label={t("toolPacks.remove", { name: label })}
          onClick={onRemove}
        >
          {t("toolPacks.removeAction")}
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          onClick={(event) => onReview(event.currentTarget)}
        >
          {t("toolPacks.review")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={disabled || (!name && (!pack.data || pack.isError))}
          onClick={() => {
            onOpen();
            navigate(packProjectPath(reference.project_id, harnessId));
          }}
        >
          {t("toolPacks.openPack")}
        </Button>
      </div>
    </li>
  );
}

function PackReview({
  projectId,
  harnessId,
  previous,
  agent,
  disabled,
  onAccept,
  onOpen,
}: {
  projectId: string;
  harnessId: string;
  previous?: ToolPackReference;
  agent?: FlowType;
  disabled?: boolean;
  onAccept: (reference: ToolPackReference) => void;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const pack = useProjectToolPack({ projectId });
  const before = previous ? appliedPackTools(agent, previous) : [];
  if (pack.isError)
    return (
      <div role="alert" className="space-y-3 py-4 text-sm">
        <p>{t("toolPacks.unavailable")}</p>
        <Button variant="outline" size="sm" onClick={() => void pack.refetch()}>
          {t("toolPacks.retry")}
        </Button>
      </div>
    );
  if (!pack.data)
    return (
      <p role="status" className="py-4 text-sm">
        {t("toolPacks.loading")}
      </p>
    );
  const manifest = pack.data;
  return (
    <>
      <div className="min-h-0 space-y-4 overflow-y-auto py-2">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold">{manifest.name}</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onOpen();
              navigate(packProjectPath(projectId, harnessId));
            }}
          >
            {t("toolPacks.openPack")}
          </Button>
        </div>
        <dl className="space-y-2 rounded-md bg-muted p-3 text-xs">
          {previous && (
            <div>
              <dt>{t("toolPacks.reviewedRevision")}</dt>
              <dd className="break-all font-mono">{previous.revision}</dd>
            </div>
          )}
          <div>
            <dt>{t("toolPacks.packRevision")}</dt>
            <dd className="break-all font-mono">
              {manifest.reference.revision}
            </dd>
          </div>
        </dl>
        {previous && !before && (
          <p className="text-sm text-muted-foreground">
            {t("toolPacks.previousUnavailable")}
          </p>
        )}
        <ul className="divide-y divide-border">
          {exportChanges(before, manifest.tools).map(
            ({ tool, before: old, status }) => (
              <li key={tool.flow_id} className="space-y-2 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="break-words text-sm font-medium">
                    {tool.name}
                  </span>
                  {status && (
                    <span className="text-xs text-muted-foreground">
                      {t(`toolPacks.${status}`)}
                    </span>
                  )}
                </div>
                {old &&
                  status === "updated" &&
                  (old.name !== tool.name ||
                    old.description !== tool.description) && (
                    <p className="break-words text-xs text-muted-foreground">
                      <del>
                        {old.name}: {old.description}
                      </del>
                    </p>
                  )}
                <p className="break-words text-xs text-muted-foreground">
                  {tool.description}
                </p>
                <details className="text-xs">
                  <summary className="cursor-pointer">
                    {t("toolPacks.flowRevision")}
                  </summary>
                  {old && old.revision !== tool.revision && (
                    <p className="break-all font-mono text-muted-foreground">
                      <del>{old.revision}</del>
                    </p>
                  )}
                  <p className="break-all font-mono">{tool.revision}</p>
                </details>
                {status !== "removed" && (
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => {
                      onOpen();
                      navigate(`/flow/${encodeURIComponent(tool.flow_id)}`);
                    }}
                  >
                    {t("toolPacks.openFlow")}
                  </Button>
                )}
              </li>
            ),
          )}
        </ul>
        {!manifest.tools.length && (
          <p className="text-sm text-muted-foreground">
            {t("toolPacks.emptyExports")}
          </p>
        )}
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
        <p className="text-xs text-muted-foreground">
          {t("toolPacks.saveHint")}
        </p>
        <Button
          size="sm"
          disabled={disabled || pack.isFetching}
          onClick={() => onAccept(manifest.reference)}
        >
          {t("toolPacks.accept")}
        </Button>
      </div>
    </>
  );
}

export function HarnessReturn({ onOpen }: { onOpen: () => void }) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const harnessId = new URLSearchParams(window.location.search).get(
    "fromHarness",
  );
  return harnessId ? (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        onOpen();
        navigate(packProjectPath(harnessId));
      }}
    >
      {t("toolPacks.returnHarness")}
    </Button>
  ) : null;
}
