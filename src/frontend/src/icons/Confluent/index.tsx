import type React from "react";
import { forwardRef } from "react";
import SvgConfluent from "./Confluent";

export const ConfluentIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ isDark?: boolean }>
>((props, ref) => {
  return <SvgConfluent ref={ref} {...props} />;
});
