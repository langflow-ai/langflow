import type React from "react";
import { forwardRef } from "react";
import { MicIcon } from "lucide-react"; // Using mic icon as placeholder

export const VLMRunIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <MicIcon ref={ref} {...props} />;
});