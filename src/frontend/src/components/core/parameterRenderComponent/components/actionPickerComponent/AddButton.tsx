import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
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

export function ActionPickerAddButton({
  selected,
  options = [],
  combobox = true,
  disabled,
  onAdd,
  testId,
}: {
  selected: string[];
  options?: string[];
  combobox?: boolean;
  disabled?: boolean;
  onAdd: (action: string) => void;
  testId?: string;
}): JSX.Element {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const available = options.filter((o) => !selected.includes(o));
  const trimmed = search.trim();
  const canAddCustom =
    combobox &&
    trimmed !== "" &&
    !options.includes(trimmed) &&
    !selected.includes(trimmed);

  const add = (action: string) => {
    if (!action) return;
    onAdd(action);
    setSearch("");
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-label={t("multiselect.chooseOption")}
          data-testid={`actionpicker-add-${testId ?? ""}`}
          className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border",
            "text-muted-foreground hover:bg-muted hover:text-foreground",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          <ForwardedIconComponent name="Plus" className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-52 p-0">
        <Command>
          <CommandInput
            placeholder={t("input.searchOptions")}
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            {!canAddCustom && (
              <CommandEmpty>{t("multiselect.noValuesFound")}</CommandEmpty>
            )}
            <CommandGroup>
              {available.map((option) => (
                <CommandItem
                  key={option}
                  value={option}
                  onSelect={() => add(option)}
                  data-testid={`action-option-${option}`}
                >
                  {option}
                </CommandItem>
              ))}
              {canAddCustom && (
                <CommandItem value={trimmed} onSelect={() => add(trimmed)}>
                  {`Add "${trimmed}"`}
                </CommandItem>
              )}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
