import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { QUIET_SELECT_TRIGGER } from "@/pages/MainPage/pages/evalsPage/utils/styles";
import type { FlowVersionEntry } from "@/types/flow/version";
import { cn } from "@/utils/utils";
import { LATEST_VERSION } from "./useEvaluateFlowForm";

interface MoreOptionsProps {
  name: string;
  onName: (value: string) => void;
  versionId: string;
  onVersion: (value: string) => void;
  versions: FlowVersionEntry[];
  threshold: number;
  onThreshold: (value: number) => void;
}

function flowVersionOptionLabel(version: FlowVersionEntry): string {
  return version.description
    ? `${version.version_tag} · ${version.description}`
    : version.version_tag;
}

/** Settings with a sensible default, folded away; the toggle shows the values in use. */
export default function MoreOptions({
  name,
  onName,
  versionId,
  onVersion,
  versions,
  threshold,
  onThreshold,
}: MoreOptionsProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const pinned = versions.find((version) => version.id === versionId);
  const summary = t("evals.evaluate.moreOptionsSummary", {
    version: pinned ? pinned.version_tag : t("evals.evaluate.latestShort"),
    threshold,
  });

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 self-start rounded-sm text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        data-testid="evaluate-more-options"
      >
        <ForwardedIconComponent
          name="ChevronRight"
          aria-hidden="true"
          className={cn(
            "h-4 w-4 transition-transform motion-reduce:transition-none",
            open && "rotate-90",
          )}
        />
        <span className="font-medium">{t("evals.evaluate.moreOptions")}</span>
        <span className="text-muted-foreground">{summary}</span>
      </button>
      {/* A display utility outranks the `hidden` attribute, so the closed panel needs the class too. */}
      <div
        id={panelId}
        hidden={!open}
        className={cn("flex flex-col gap-4 border-l pl-4", !open && "hidden")}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="evaluation-name">{t("evals.evaluate.name")}</Label>
            <Input
              id="evaluation-name"
              className="h-9"
              value={name}
              maxLength={255}
              placeholder={t("evals.evaluate.namePlaceholder")}
              onChange={(event) => onName(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="evaluation-version">
              {t("evals.evaluate.version")}
            </Label>
            <Select value={versionId} onValueChange={onVersion}>
              <SelectTrigger
                id="evaluation-version"
                data-testid="evaluate-version"
                className={cn("h-9", QUIET_SELECT_TRIGGER)}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={LATEST_VERSION}>
                  {t("evals.evaluate.latestVersion")}
                </SelectItem>
                {versions.map((version) => (
                  <SelectItem key={version.id} value={version.id}>
                    {flowVersionOptionLabel(version)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Label htmlFor="evaluation-threshold" className="shrink-0">
            {t("evals.evaluate.threshold")}
          </Label>
          <div className="w-24 shrink-0">
            <Input
              id="evaluation-threshold"
              type="number"
              min={0}
              max={1}
              step={0.05}
              className="h-9 w-full"
              value={threshold}
              aria-describedby="evaluation-threshold-hint"
              onChange={(event) => {
                const value = Number(event.target.value);
                if (!Number.isNaN(value)) {
                  onThreshold(Math.min(1, Math.max(0, value)));
                }
              }}
            />
          </div>
          <span
            id="evaluation-threshold-hint"
            className="text-xs text-muted-foreground"
          >
            {t("evals.evaluate.thresholdHint")}
          </span>
        </div>
      </div>
    </div>
  );
}
