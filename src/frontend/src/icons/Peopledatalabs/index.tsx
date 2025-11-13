import React, { forwardRef } from "react";
import PeopledatalabsIconSVG from "./peopledatalabs";

export const PeopledatalabsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return (
    <PeopledatalabsIconSVG
      ref={ref}
      {...props}
      style={{ width: 20, height: 20 }}
    />
  );
});
