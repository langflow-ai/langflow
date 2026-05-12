import { useState } from "react";
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

const KEY_PATTERN = /^[a-z0-9_]{1,32}$/;
const MAX_KEYS = 16;
const MAX_VALUE_LENGTH = 256;

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
 * Mirrors the rules enforced by the backend ``parse_user_metadata``
 * helper: lowercase alphanumeric+underscore keys (≤32 chars),
 * non-reserved, ≤16 keys total, ≤256-char values.
 */
export function MetadataEditor({
  pairs,
  onPairsChange,
  disabled = false,
  testIdScope = "kb",
}: MetadataEditorProps) {
  const [errors, setErrors] = useState<Record<number, string>>({});

  const updatePair = (index: number, patch: Partial<MetadataPair>) => {
    const next = pairs.map((pair, i) =>
      i === index ? { ...pair, ...patch } : pair,
    );
    onPairsChange(next);
    setErrors((prev) => {
      // Clearing the row also clears any stale validation message for it.
      if (!patch.key && !patch.value) return prev;
      const { [index]: _drop, ...rest } = prev;
      return rest;
    });
  };

  const addPair = () => {
    if (pairs.length >= MAX_KEYS) return;
    onPairsChange([...pairs, { key: "", value: "" }]);
  };

  const removePair = (index: number) => {
    onPairsChange(pairs.filter((_, i) => i !== index));
    setErrors((prev) => {
      const { [index]: _drop, ...rest } = prev;
      return rest;
    });
  };

  const validateKey = (index: number, key: string) => {
    if (!key) return;
    if (!KEY_PATTERN.test(key)) {
      setErrors((prev) => ({
        ...prev,
        [index]: "Keys must be 1-32 lowercase letters, digits, or underscores.",
      }));
      return;
    }
    const duplicate = pairs.some((pair, i) => i !== index && pair.key === key);
    if (duplicate) {
      setErrors((prev) => ({ ...prev, [index]: "Duplicate key." }));
      return;
    }
    setErrors((prev) => {
      const { [index]: _drop, ...rest } = prev;
      return rest;
    });
  };

  return (
    <div className="flex flex-col gap-2">
      <Label className="flex items-center gap-1 text-xs text-muted-foreground">
        Custom Fields
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
              Optional key/value tags applied to every chunk produced by this
              ingestion. Use lowercase letters, digits, or underscores for keys
              (max 32 characters). Values are stored as strings.
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
            No metadata fields added.
          </div>
        )}

        {pairs.map((pair, index) => (
          <div key={index} className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Input
                placeholder="key"
                value={pair.key}
                onChange={(e) => updatePair(index, { key: e.target.value })}
                onBlur={() => validateKey(index, pair.key)}
                className={cn(
                  "h-8 flex-1",
                  errors[index] && "border-destructive",
                )}
                data-testid={`${testIdScope}-metadata-key-${index}`}
                disabled={disabled}
              />
              <Input
                placeholder="value"
                value={pair.value}
                onChange={(e) => updatePair(index, { value: e.target.value })}
                maxLength={MAX_VALUE_LENGTH}
                className="h-8 flex-1"
                data-testid={`${testIdScope}-metadata-value-${index}`}
                disabled={disabled}
              />
              <Button
                type="button"
                variant="ghost"
                size="iconSm"
                onClick={() => removePair(index)}
                aria-label={`Remove metadata field ${index + 1}`}
                data-testid={`${testIdScope}-metadata-remove-${index}`}
                disabled={disabled}
              >
                <ForwardedIconComponent name="X" className="h-3.5 w-3.5" />
              </Button>
            </div>
            {errors[index] && (
              <span className="text-xs text-destructive">{errors[index]}</span>
            )}
          </div>
        ))}

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
          Add field
        </Button>
      </div>
    </div>
  );
}

/**
 * Convert UI pairs into the JSON-string payload expected by the backend.
 * Strips empty rows; collapses to ``""`` when nothing is set so the API
 * route can skip parsing entirely.
 */
export function metadataPairsToFormValue(pairs: MetadataPair[]): string {
  const populated = pairs
    .map((pair) => ({ key: pair.key.trim(), value: pair.value.trim() }))
    .filter((pair) => pair.key && pair.value && KEY_PATTERN.test(pair.key));
  if (populated.length === 0) return "";
  const result: Record<string, string> = {};
  for (const pair of populated) {
    result[pair.key] = pair.value;
  }
  return JSON.stringify(result);
}
