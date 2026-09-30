import type React from "react";
import { forwardRef } from "react";
import SvgClickhouseIcon from "./Clickhouse";

export const ClickhouseIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgClickhouseIcon ref={ref} {...props} />;
});
