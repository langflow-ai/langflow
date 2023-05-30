import React, { forwardRef } from "react";
import { ReactComponent as NotionSVG } from "./Notion-logo.svg";

export const NotionIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <NotionSVG ref={ref} {...props} />;
});
