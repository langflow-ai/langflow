import React, { forwardRef } from "react";
import { ReactComponent as EvernoteSVG } from "./evernote-icon.svg";

export const EvernoteIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <EvernoteSVG ref={ref} {...props} />;
});
