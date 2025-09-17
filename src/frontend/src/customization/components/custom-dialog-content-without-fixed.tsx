import * as DialogPrimitive from "@radix-ui/react-dialog";
import { DialogContent } from "@radix-ui/react-dialog";
import React from "react";

export const DialogContentWithouFixed = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    hideTitle?: boolean;
    closeButtonClassName?: string;
  }
>(
  (
    { className, children, hideTitle = false, closeButtonClassName, ...props },
    ref,
  ) => {
    return <></>;
  },
);
DialogContent.displayName = DialogPrimitive.Content.displayName;

export default DialogContentWithouFixed;
