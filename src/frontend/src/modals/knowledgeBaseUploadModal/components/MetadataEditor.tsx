import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils/utils";
import {
  filterValidMetadataPairs,
  MAX_KEYS,
  MAX_VALUE_LENGTH,
  validateMetadataPairs,
} from "./metadataValidation";

export interface MetadataPair {
  key: string;
  value: string;
}

interface MetadataEditorProps {
  pairs: MetadataPair[];
  onPairsChange: (pairs: MetadataPair[]) => void;
  disabled?: boolean;
  /**
   * Identifier suffix for ``data-testid`` attributes. Lets the same
   * editor render twice on one screen (run-level + per-file) without
   * test selectors colliding.
   */
  testIdScope?: string;
}

/**
 * Compact key/value editor for user-supplied KB metadata.
 *
 * Validation lives in ``metadataValidation.ts`` and is derived from the
 * current ``pairs`` prop, not local state, so a parent that wants to
 * gate "Next Step" can call ``validateMetadataPairs`` on the same array
 * and get the same answer. Mirrors the rules enforced by the backend
 * ``parse_user_metadata`` helper (≤32-char lowercase keys, no dupes,
 * ≤256-char values, ≤16 keys total).
 */
export function MetadataEditor({
  pairs,
  onPairsChange,
  disabled = false,
  testIdScope = "kb",
}: MetadataEditorProps) {
  const { t } = useTranslation();
  const validation = useMemo(() => validateMetadataPairs(pairs), [pairs]);

  const updatePair = (index: number, patch: Partial<MetadataPair>) => {
    const next = pairs.map((pair, i) =>
      i === index ? { ...pair, ...patch } : pair,
    );
    onPairsChange(next);
  };

  const addPair = () => {
    if (pairs.length >= MAX_KEYS) return;
    onPairsChange([...pairs, { key: "", value: "" }]);
  };

  const removePair = (index: number) => {
    onPairsChange(pairs.filter((_, i) => i !== index));
  };

  return (
    <div className="flex flex-col gap-2">
      <Label className="flex items-center gap-1 text-xs text-muted-foreground">
        {t("knowledge.metadataCustomFields")}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="cursor-help">
                <ForwardedIconComponent
                  name="Info"
                  className="h-3.5 w-3.5 text-muted-foreground"
                />
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-[280px]">
              {t("knowledge.metadataTooltip")}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </Label>

      <div
        className={cn(
          "flex flex-col gap-2",
          disabled && "opacity-50 pointer-events-none",
        )}
        aria-disabled={disabled}
      >
        {pairs.length === 0 && (
          <div
            className="text-xs text-muted-foreground italic"
            data-testid={`${testIdScope}-metadata-empty`}
          >
            {t("knowledge.metadataNoFields")}
          </div>
        )}

        {pairs.map((pair, index) => {
          const rowError = validation.errors[index];
          return (
            <div key={index} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Input
                  placeholder={t("knowledge.metadataKeyPlaceholder")}
                  value={pair.key}
                  onChange={(e) => updatePair(index, { key: e.target.value })}
                  className={cn("h-8 flex-1", rowError && "border-destructive")}
                  data-testid={`${testIdScope}-metadata-key-${index}`}
                  disabled={disabled}
                />
                <Input
                  placeholder={t("knowledge.metadataValuePlaceholder")}
                  value={pair.value}
                  onChange={(e) => updatePair(index, { value: e.target.value })}
                  maxLength={MAX_VALUE_LENGTH}
                  className={cn("h-8 flex-1", rowError && "border-destructive")}
                  data-testid={`${testIdScope}-metadata-value-${index}`}
                  disabled={disabled}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="iconSm"
                  onClick={() => removePair(index)}
                  aria-label={t("knowledge.metadataRemoveField", {
                    index: index + 1,
                  })}
                  data-testid={`${testIdScope}-metadata-remove-${index}`}
                  disabled={disabled}
                >
                  <ForwardedIconComponent name="X" className="h-3.5 w-3.5" />
                </Button>
              </div>
              {rowError && (
                <span
                  className="text-xs text-destructive"
                  data-testid={`${testIdScope}-metadata-error-${index}`}
                >
                  {rowError}
                </span>
              )}
            </div>
          );
        })}

        {validation.setError && (
          <span
            className="text-xs text-destructive"
            data-testid={`${testIdScope}-metadata-set-error`}
          >
            {validation.setError}
          </span>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addPair}
          disabled={disabled || pairs.length >= MAX_KEYS}
          data-testid={`${testIdScope}-metadata-add`}
          className="w-fit"
        >
          <ForwardedIconComponent name="Plus" className="mr-1 h-3.5 w-3.5" />
          {t("knowledge.metadataAddField")}
        </Button>
      </div>
    </div>
  );
}

/**
 * Convert UI pairs into the JSON-string payload expected by the backend.
 * Strips invalid / empty rows; collapses to ``""`` when nothing valid
 * remains so the API route can skip parsing entirely.
 */
export function metadataPairsToFormValue(pairs: MetadataPair[]): string {
  const populated = filterValidMetadataPairs(pairs);
  if (populated.length === 0) return "";
  const result: Record<string, string> = {};
  for (const pair of populated) {
    result[pair.key] = pair.value;
  }
  return JSON.stringify(result);
}
