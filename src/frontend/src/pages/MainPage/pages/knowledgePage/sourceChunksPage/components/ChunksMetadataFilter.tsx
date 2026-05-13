import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useGetKbMetadataKeys } from "@/controllers/API/queries/knowledge-bases/use-get-kb-metadata-keys";
import { cn } from "@/utils/utils";

const KEY_PATTERN = /^[a-z0-9_]{1,32}$/;

interface ChunksMetadataFilterProps {
  kbName: string;
  onAdd: (key: string, value: string) => void;
}

interface MetadataComboboxProps {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder: string;
  emptyMessage: string;
  testId: string;
  disabled?: boolean;
  onEnter?: () => void;
}

const MetadataCombobox = ({
  value,
  onChange,
  options,
  placeholder,
  emptyMessage,
  testId,
  disabled,
  onEnter,
}: MetadataComboboxProps) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const trimmedQuery = query.trim();
  const normalizedOptions = useMemo(
    () => options.map((option) => option.toLowerCase()),
    [options],
  );
  const showCustom =
    trimmedQuery.length > 0 &&
    !normalizedOptions.includes(trimmedQuery.toLowerCase());

  const commit = (next: string) => {
    onChange(next);
    setQuery("");
    setOpen(false);
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="w-full justify-between font-normal"
          data-testid={testId}
        >
          <span
            className={cn(
              "truncate text-left",
              value ? "text-foreground" : "text-muted-foreground",
            )}
          >
            {value || placeholder}
          </span>
          <ForwardedIconComponent
            name="ChevronDown"
            className="ml-2 h-4 w-4 shrink-0 opacity-50"
          />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[--radix-popover-trigger-width] p-0"
      >
        <Command shouldFilter>
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={placeholder}
            data-testid={`${testId}-input`}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !showCustom && options.length === 0) {
                e.preventDefault();
                if (trimmedQuery) commit(trimmedQuery);
                else onEnter?.();
              }
            }}
          />
          <CommandList>
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            {options.length > 0 && (
              <CommandGroup>
                {options.map((option) => (
                  <CommandItem
                    key={option}
                    value={option}
                    onSelect={() => commit(option)}
                    data-testid={`${testId}-option-${option}`}
                  >
                    <ForwardedIconComponent
                      name="Check"
                      className={cn(
                        "mr-2 h-4 w-4",
                        value === option ? "opacity-100" : "opacity-0",
                      )}
                    />
                    {option}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {showCustom && (
              <CommandGroup>
                <CommandItem
                  value={`__custom__${trimmedQuery}`}
                  onSelect={() => commit(trimmedQuery)}
                  data-testid={`${testId}-custom`}
                >
                  <ForwardedIconComponent
                    name="Plus"
                    className="mr-2 h-4 w-4"
                  />
                  Use “{trimmedQuery}”
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

/**
 * "+ Filter by metadata" popover for the chunks-browser metadata chips.
 *
 * Key and value pickers are shadcn comboboxes (Popover + Command). They
 * match the visual style of the surrounding shadcn `Select` controls (e.g.
 * "All sources") while still letting users type a custom key/value that is
 * not yet in the suggestion list.
 *
 * Validation mirrors the backend rules so an obviously malformed key (e.g.
 * uppercase or punctuation) is rejected before it would 422 server-side.
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
    data: metadataKeys,
    isLoading,
    refetch: refetchMetadataKeys,
  } = useGetKbMetadataKeys({ kb_name: kbName }, { enabled: open && !!kbName });

  const availableKeys = useMemo(
    () => Object.keys(metadataKeys?.keys ?? {}).sort(),
    [metadataKeys],
  );

  const valueSuggestions = useMemo(() => {
    const trimmed = key.trim();
    if (!trimmed) return [] as string[];
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

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (next && kbName) {
      void refetchMetadataKeys();
    }
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
