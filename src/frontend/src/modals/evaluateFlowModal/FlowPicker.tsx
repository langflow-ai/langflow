import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils/utils";

interface FlowPickerProps {
  id: string;
  flows: { id: string; name: string }[];
  value: string;
  onChange: (flowId: string) => void;
}

/** A searchable flow list: users can have dozens of flows, too many for a plain select. */
export default function FlowPicker({
  id,
  flows,
  value,
  onChange,
}: FlowPickerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const selected = flows.find((flow) => flow.id === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="primary"
          role="combobox"
          aria-expanded={open}
          data-testid="evaluate-flow"
          className="h-8 w-full justify-between px-4 font-normal focus-visible:ring-1 focus-visible:ring-offset-0"
        >
          <span
            className={cn("truncate", !selected && "text-muted-foreground")}
          >
            {selected?.name ?? t("evals.evaluate.chooseFlow")}
          </span>
          <ForwardedIconComponent
            name="ChevronsUpDown"
            className="h-4 w-4 shrink-0 opacity-60"
          />
        </Button>
      </PopoverTrigger>
      <PopoverContentWithoutPortal
        align="start"
        className="w-[--radix-popover-trigger-width] p-0"
      >
        <Command
          // Plain substring match: fuzzy matching surfaces unrelated flow names.
          filter={(itemValue, search) =>
            itemValue.toLowerCase().includes(search.trim().toLowerCase())
              ? 1
              : 0
          }
        >
          <CommandInput
            placeholder={t("evals.evaluate.searchFlows")}
            aria-label={t("evals.evaluate.searchFlows")}
            data-testid="evaluate-flow-search"
          />
          <CommandList className="max-h-64">
            <CommandEmpty>{t("evals.evaluate.noFlows")}</CommandEmpty>
            {flows.map((flow) => (
              <CommandItem
                key={flow.id}
                value={`${flow.name} ${flow.id}`}
                onSelect={() => {
                  onChange(flow.id);
                  setOpen(false);
                }}
                className="flex items-center justify-between gap-2"
              >
                <span className="truncate">{flow.name}</span>
                {flow.id === value && (
                  <ForwardedIconComponent
                    name="Check"
                    aria-hidden="true"
                    className="h-4 w-4 shrink-0"
                  />
                )}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContentWithoutPortal>
    </Popover>
  );
}
