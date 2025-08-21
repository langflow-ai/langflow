import { forwardRef } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

export const MenuEllipsisButton = forwardRef<HTMLButtonElement>(
  (props, ref) => {
    return (
      <Button
        variant="menu"
        size="icon"
        className="duration-75 text-muted-foreground"
        ref={ref}
        {...props}
      >
        <ForwardedIconComponent name="EllipsisVertical" />
      </Button>
    );
  }
);
