import React, { forwardRef } from "react";
import SvgPostgres from "./Postgres";

export const PostgresIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPostgres ref={ref} {...props} />;
});
