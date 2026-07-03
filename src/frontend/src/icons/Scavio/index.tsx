import type React from "react";
import { forwardRef } from "react";
import Scavio from "./Scavio";

export const ScavioIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <Scavio ref={ref} {...props} />;
});
