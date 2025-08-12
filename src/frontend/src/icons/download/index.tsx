import React, { forwardRef } from "react";
import DownloadIconSVG from "./download";

export const DownloadIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DownloadIconSVG ref={ref} {...props} />;
});