import type React from "react";
import { forwardRef, useId } from "react";
import Context from "./ContextIcon";

export const ContextIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const maskId = `context-cutout-${useId().replaceAll(":", "")}`;

  return <Context ref={ref} maskId={maskId} {...props} />;
});
