import { forwardRef } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

export const HeaderButton = forwardRef<
  HTMLButtonElement,
  { icon: string; onClick?: () => void }
>(({ icon, onClick, ...props }, ref) => {
  return (
    <Button
      variant="ghost"
      size="icon"
      className="flex h-8 w-8 items-center gap-2 text-muted-foreground"
      ref={ref}
      onClick={onClick}
      {...props}
    >
      <ForwardedIconComponent name={icon} className="h-4 w-4" />
    </Button>
  );
});
