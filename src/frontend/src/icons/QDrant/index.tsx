import React, { forwardRef } from "react";
import { ReactComponent as QDrantSVG } from "./QDrant.svg";

export const QDrantIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <QDrantSVG ref={ref} {...props} />;
});
