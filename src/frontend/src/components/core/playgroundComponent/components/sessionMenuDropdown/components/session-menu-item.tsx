import { forwardRef } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";

export const SessionMenuItem = forwardRef<
  HTMLDivElement,
  {
    onSelect: () => void;
    className?: string;
    icon?: string;
    children: React.ReactNode;
    disabled?: boolean;
  }
>(({ onSelect, className, icon, children, disabled }, ref) => {
  return (
    <DropdownMenuItem
      className={cn("!text-mmd font-normal gap-2 px-2.5 py-2", className)}
      onSelect={onSelect}
      disabled={disabled}
      onClick={(event) => event.stopPropagation()}
      ref={ref}
    >
      {icon && <ForwardedIconComponent name={icon} className="w-4 h-4" />}
      {children}
    </DropdownMenuItem>
  );
});
