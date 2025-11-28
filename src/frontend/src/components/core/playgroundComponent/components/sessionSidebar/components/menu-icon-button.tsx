import { forwardRef } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button, type ButtonProps } from "@/components/ui/button";

interface MenuIconButtonProps extends ButtonProps {
  icon: string;
}

export const MenuIconButton = forwardRef<
  HTMLButtonElement,
  MenuIconButtonProps
>(({ icon, ...props }, ref) => {
  return (
    <Button
      variant="menu"
      size="icon"
      className="duration-75 text-muted-foreground no-focus-visible"
      ref={ref}
      {...props}
    >
      <ForwardedIconComponent name={icon} />
    </Button>
  );
});
