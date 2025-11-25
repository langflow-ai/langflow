import React, { forwardRef } from "react";
import SnowflakeIconSVG from "./snowflake";

export const SnowflakeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return (
    <SnowflakeIconSVG ref={ref} {...props} style={{ width: 12, height: 12 }} />
  );
});
