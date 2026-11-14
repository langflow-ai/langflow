import { useTranslation } from "react-i18next";
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

// Long lists scroll inside the space left on screen instead of running off it.
const LIST_HEIGHT =
  "max-h-[min(20rem,var(--radix-select-content-available-height))]";

import { LATEST_VERSION } from "./useEvaluateFlowForm";

interface RunSettingsProps {
  name: string;
  onName: (value: string) => void;
  versionId: string;
  onVersion: (value: string) => void;
  versions: FlowVersionEntry[];
}

function flowVersionOptionLabel(version: FlowVersionEntry): string {
  return version.description
    ? `${version.version_tag} · ${version.description}`
    : version.version_tag;
}

/** The evaluation's name and the flow version it runs; both have defaults. */
export default function RunSettings({
  name,
  onName,
  versionId,
  onVersion,
  versions,
}: RunSettingsProps) {
  const { t } = useTranslation();
  return (
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
          <SelectContent className={LIST_HEIGHT}>
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
  );
}
