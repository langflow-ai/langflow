import type React from "react";
import { forwardRef } from "react";
import DataBricksSVG from "./DataBricks";

export const DataBricksIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DataBricksSVG ref={ref} {...props} />;
});

export default DataBricksIcon;
