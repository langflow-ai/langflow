import React, { forwardRef } from "react";
import SvgPostgres from "./Redis";

export const PostgresIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPostgres ref={ref} {...props} />;
});
