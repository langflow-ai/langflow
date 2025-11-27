import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

type SortOption = {
  label: string;
  value: string;
  icon?: string; // optional if you ever need icons later
};

export function SortByDropdown({
  value,
  onChange,
  options,
  placeholder = "Sort By",
}: {
  value: string;
  onChange: (v: string) => void;
  options: SortOption[];
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="xs"
          className="w-[120px] h-8 px-2 gap-1 justify-between !rounded-[6px]"
        >
          <p className="flex items-center gap-2">
            <ForwardedIconComponent name="ArrowUpDown" className="!h-3 !w-3" />
            <span>{placeholder}</span>
          </p>
          <ForwardedIconComponent name="ChevronDown" className="!h-4 !w-4" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="min-w-[160px]">
        {options.map((opt) => (
          <DropdownMenuItem
            key={opt.value}
            className={cn(
              "flex items-center justify-between gap-4 text-sm cursor-pointer",
              value === opt.value && "bg-accent"
            )}
            onClick={() => onChange(opt.value)}
          >
            <span>{opt.label}</span>
            <div className="flex items-center">
              <ForwardedIconComponent
                name="ArrowUp"
                className="h-3 w-3 dark:text-white"
              />
              <ForwardedIconComponent
                name="ArrowDown"
                className="h-3 w-3 dark:text-white"
              />
            </div>

            {/* optional icons if needed later */}
            {opt.icon && (
              <ForwardedIconComponent name={opt.icon} className="h-3 w-3" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
