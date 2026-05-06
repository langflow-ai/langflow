import { useId, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useGetKbMetadataKeys } from "@/controllers/API/queries/knowledge-bases/use-get-kb-metadata-keys";

const KEY_PATTERN = /^[a-z0-9_]{1,32}$/;

interface ChunksMetadataFilterProps {
  /** Knowledge base name — used to fetch the available metadata keys. */
  kbName: string;
  /** Called when the user submits a key/value pair. */
  onAdd: (key: string, value: string) => void;
}

/**
 * "+ Filter by metadata" popover for the chunks-browser metadata chips.
 *
 * Both inputs are bound to a `<datalist>` populated from the new
 * `/metadata/keys` endpoint so the user gets self-documenting key + value
 * suggestions on click and free-text typing for keys not in the list.
 *
 * Validation mirrors the backend rules so an obviously malformed key (e.g.
 * uppercase or punctuation) is rejected before it would 422 server-side.
 * Submitting closes the popover and clears the inputs so the user can chain
 * multiple chips without re-opening it manually.
 */
export const ChunksMetadataFilter = ({
  kbName,
  onAdd,
}: ChunksMetadataFilterProps) => {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const keyListId = useId();
  const valueListId = useId();

  const {
    data: metadataKeys,
    isLoading,
    refetch: refetchMetadataKeys,
  } = useGetKbMetadataKeys({ kb_name: kbName }, { enabled: open && !!kbName });

  const availableKeys = useMemo(
    () => Object.keys(metadataKeys?.keys ?? {}).sort(),
    [metadataKeys],
  );

  // Distinct values for the currently typed key, when that key matches one
  // of the keys returned from the server. Falls back to no suggestions for
  // free-typed keys.
  const valueSuggestions = useMemo(() => {
    const trimmed = key.trim();
    if (!trimmed) return [];
    return metadataKeys?.keys?.[trimmed] ?? [];
  }, [key, metadataKeys]);

  const submit = () => {
    const trimmedKey = key.trim();
    const trimmedValue = value.trim();
    if (!trimmedKey || !trimmedValue) {
      setError("Key and value are required.");
      return;
    }
    if (!KEY_PATTERN.test(trimmedKey)) {
      setError("Key must be 1-32 lowercase letters, digits, or underscores.");
      return;
    }
    onAdd(trimmedKey, trimmedValue);
    setKey("");
    setValue("");
    setError(null);
    setOpen(false);
  };

  const hasKeys = availableKeys.length > 0;

  // Refetch on every popover open so a fresh ingestion's new keys/values
  // surface without a hard page refresh. The `enabled` flag re-arms the
  // query when the popover opens; calling `refetch` here forces a network
  // round-trip even when React Query already has cached data, which is the
  // case after the user closes and re-opens the popover within the same
  // browser session.
  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (next && kbName) {
      void refetchMetadataKeys();
    }
  };

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
          <Input
            list={keyListId}
            placeholder={
              isLoading
                ? "Loading keys..."
                : hasKeys
                  ? "Pick or type a key"
                  : "key"
            }
            value={key}
            onChange={(e) => setKey(e.target.value)}
            data-testid="chunks-metadata-filter-key"
            autoFocus
          />
          <datalist
            id={keyListId}
            data-testid="chunks-metadata-filter-key-options"
          >
            {availableKeys.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
          <Input
            list={valueListId}
            placeholder={
              valueSuggestions.length > 0 ? "Pick or type a value" : "value"
            }
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            data-testid="chunks-metadata-filter-value"
          />
          <datalist
            id={valueListId}
            data-testid="chunks-metadata-filter-value-options"
          >
            {valueSuggestions.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
          {!isLoading && !hasKeys && (
            <span
              className="text-xs text-muted-foreground"
              data-testid="chunks-metadata-filter-empty"
            >
              No metadata keys found in this KB. Type a key to filter anyway.
            </span>
          )}
          {metadataKeys?.truncated && (
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
