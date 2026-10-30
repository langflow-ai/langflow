import { useLayoutEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";

export interface RowAction {
  label: string;
  icon: string;
  onSelect: () => void;
  destructive?: boolean;
  disabled?: boolean;
}

interface RowActionsMenuProps {
  label: string;
  actions: RowAction[];
  testId?: string;
}

/**
 * Same pattern as the knowledge-base row menu: portal into `main` so the open
 * menu stays inside a landmark, resolved on open because AG Grid can mount a
 * cell renderer before it is attached under `main`.
 */
export default function RowActionsMenu({
  label,
  actions,
  testId,
}: RowActionsMenuProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [container, setContainer] = useState<HTMLElement | null>(null);
  const resolveContainer = () =>
    rootRef.current?.closest<HTMLElement>("main") ??
    document.querySelector<HTMLElement>("main");

  useLayoutEffect(() => {
    setContainer(resolveContainer());
  }, []);

  return (
    <div ref={rootRef} className="flex items-center justify-end">
      <DropdownMenu
        open={open}
        onOpenChange={(next) => {
          if (next) setContainer(resolveContainer());
          setOpen(next);
        }}
      >
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label={label}
            data-testid={testId}
            onClick={(event) => event.stopPropagation()}
          >
            <ForwardedIconComponent
              name="EllipsisVertical"
              className="h-4 w-4 text-primary"
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" container={container ?? undefined}>
          {actions.map((action) => (
            <DropdownMenuItem
              key={action.label}
              disabled={action.disabled}
              onClick={(event) => {
                event.stopPropagation();
                action.onSelect();
              }}
              className={cn(
                action.destructive && "text-destructive focus:text-destructive",
              )}
            >
              <ForwardedIconComponent
                name={action.icon}
                className="mr-2 h-4 w-4"
              />
              {action.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
