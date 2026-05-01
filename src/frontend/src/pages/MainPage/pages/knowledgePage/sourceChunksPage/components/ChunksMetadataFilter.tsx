import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

const KEY_PATTERN = /^[a-z0-9_]{1,32}$/;

interface ChunksMetadataFilterProps {
  /** Called when the user submits a key/value pair. */
  onAdd: (key: string, value: string) => void;
}

/**
 * Compact "+ Add filter" popover for the chunks-browser metadata chips.
 *
 * Validation mirrors the backend rules so an obviously malformed key (e.g.
 * uppercase or punctuation) is rejected before it would 422 server-side.
 * Submitting closes the popover and clears the inputs so the user can chain
 * multiple chips without re-opening it manually.
 */
export const ChunksMetadataFilter = ({ onAdd }: ChunksMetadataFilterProps) => {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

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

  return (
    <Popover open={open} onOpenChange={setOpen}>
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
            placeholder="key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            data-testid="chunks-metadata-filter-key"
            autoFocus
          />
          <Input
            placeholder="value"
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
