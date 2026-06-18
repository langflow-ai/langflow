import React, { forwardRef } from "react";
import SvgDataForB2B from "./DataForB2BIcon";

export const DataForB2BIcon = forwardRef<
  HTMLImageElement,
  React.ComponentProps<"img">
>((props, ref) => {
  return <SvgDataForB2B ref={ref} {...props} />;
});

DataForB2BIcon.displayName = "DataForB2BIcon";
