import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useChunksMetadataFilter } from "./hooks/useChunksMetadataFilter";
import { MetadataCombobox } from "./MetadataCombobox";
import { validateMetadataFilter } from "./metadataFilterValidation";

interface ChunksMetadataFilterProps {
  kbName: string;
  onAdd: (key: string, value: string) => void;
}

/**
 * "+ Filter by metadata" popover for the chunks-browser metadata chips.
 *
 * Orchestrates the outer popover, form state, and submit. The combobox
 * UI, data fetching, and validation each live in their own modules
 * (`MetadataCombobox`, `useChunksMetadataFilter`, `metadataFilterValidation`).
 */
export const ChunksMetadataFilter = ({
  kbName,
  onAdd,
}: ChunksMetadataFilterProps) => {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const {
    availableKeys,
    valueSuggestions,
    isLoading,
    hasKeys,
    truncated,
    refetch,
  } = useChunksMetadataFilter({
    kbName,
    enabled: open,
    selectedKey: key,
  });

  const submit = () => {
    const result = validateMetadataFilter(key, value);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    onAdd(result.key, result.value);
    setKey("");
    setValue("");
    setError(null);
    setOpen(false);
  };

  // Refetch on every popover open so a fresh ingestion's new keys/values
  // surface without a hard page refresh.
  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (next && kbName) refetch();
  };

  const keyPlaceholder = isLoading
    ? "Loading keys..."
    : hasKeys
      ? "Pick or type a key"
      : "Type a key";

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          data-testid="chunks-metadata-add-filter"
        >
          <ForwardedIconComponent name="Plus" className="mr-1 h-3.5 w-3.5" />
          Filter by metadata
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="end">
        <div className="flex flex-col gap-2">
          <MetadataCombobox
            value={key}
            onChange={(next) => {
              setKey(next);
              setError(null);
              setValue("");
            }}
            options={availableKeys}
            placeholder={keyPlaceholder}
            emptyMessage={
              isLoading
                ? "Loading keys..."
                : hasKeys
                  ? "No matching key. Press Enter or pick to use as typed."
                  : "Type a key to filter."
            }
            testId="chunks-metadata-filter-key"
          />
          <MetadataCombobox
            value={value}
            onChange={(next) => {
              setValue(next);
              setError(null);
            }}
            options={valueSuggestions}
            placeholder={
              valueSuggestions.length > 0
                ? "Pick or type a value"
                : "Type a value"
            }
            emptyMessage={
              valueSuggestions.length > 0
                ? "No matching value. Press Enter or pick to use as typed."
                : "Type a value."
            }
            testId="chunks-metadata-filter-value"
            disabled={!key.trim()}
            onEnter={submit}
          />
          {!isLoading && !hasKeys && (
            <span
              className="text-xs text-muted-foreground"
              data-testid="chunks-metadata-filter-empty"
            >
              No metadata keys found in this KB. Type a key to filter anyway.
            </span>
          )}
          {truncated && (
            <span
              className="text-xs text-muted-foreground"
              data-testid="chunks-metadata-filter-truncated"
            >
              Showing first 50 values per key.
            </span>
          )}
          {error && <span className="text-xs text-destructive">{error}</span>}
          <Button
            onClick={submit}
            size="sm"
            data-testid="chunks-metadata-filter-submit"
          >
            Add filter
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
};
