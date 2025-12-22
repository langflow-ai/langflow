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
import { cn } from "@/utils/utils";

export type ModelOption = {
  slug: string;
  name: string;
  vendor?: string;
  context_length?: number;
};

interface ModelSelectorProps {
  models: ModelOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  isLoading?: boolean;
}

export default function ModelSelector({
  models,
  value,
  onChange,
  disabled,
  isLoading,
}: ModelSelectorProps) {
  const [open, setOpen] = useState(false);

  const selectedModel = useMemo(
    () => models.find((m) => m.slug === value),
    [models, value],
  );

  const displayName = selectedModel?.name ?? value ?? "Select model";

  const groupedModels = useMemo(() => {
    const groups: Record<string, ModelOption[]> = {};
    for (const m of models) {
      const vendor = m.vendor || "Other";
      if (!groups[vendor]) groups[vendor] = [];
      groups[vendor].push(m);
    }
    return groups;
  }, [models]);

  const hasGroups = Object.keys(groupedModels).length > 1;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          role="combobox"
          aria-expanded={open}
          className="h-6 justify-between gap-1 px-2 text-xs font-normal text-muted-foreground hover:text-foreground"
          disabled={disabled || isLoading}
        >
          <span className="max-w-[120px] truncate">
            {isLoading ? "Loading…" : displayName}
          </span>
          <ForwardedIconComponent
            name="ChevronsUpDown"
            className="h-3 w-3 shrink-0 opacity-50"
          />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[280px] p-0"
        align="start"
        side="bottom"
        sideOffset={4}
      >
        <Command
          filter={(value, search) => {
            const model = models.find((m) => m.slug === value);
            if (!model) return 0;
            const searchLower = search.toLowerCase();
            if (model.name.toLowerCase().includes(searchLower)) return 1;
            if (model.slug.toLowerCase().includes(searchLower)) return 1;
            if (model.vendor?.toLowerCase().includes(searchLower)) return 1;
            return 0;
          }}
        >
          <CommandInput placeholder="Search models…" className="h-9" />
          <CommandList>
            <CommandEmpty>No models found.</CommandEmpty>
            {hasGroups ? (
              Object.entries(groupedModels).map(([vendor, vendorModels]) => (
                <CommandGroup key={vendor} heading={vendor}>
                  {vendorModels.map((m) => (
                    <CommandItem
                      key={m.slug}
                      value={m.slug}
                      onSelect={() => {
                        onChange(m.slug);
                        setOpen(false);
                      }}
                      className="flex items-center justify-between"
                    >
                      <span className="truncate">{m.name}</span>
                      {m.slug === value && (
                        <ForwardedIconComponent
                          name="Check"
                          className="h-4 w-4 text-primary"
                        />
                      )}
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))
            ) : (
              <CommandGroup>
                {models.map((m) => (
                  <CommandItem
                    key={m.slug}
                    value={m.slug}
                    onSelect={() => {
                      onChange(m.slug);
                      setOpen(false);
                    }}
                    className="flex items-center justify-between"
                  >
                    <span className="truncate">{m.name}</span>
                    {m.slug === value && (
                      <ForwardedIconComponent
                        name="Check"
                        className="h-4 w-4 text-primary"
                      />
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
