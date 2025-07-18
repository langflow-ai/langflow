import type React from "react";
import { forwardRef } from "react";
import SvgDropbox from "./Dropbox";

export const DropboxIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgDropbox ref={ref} {...props} />;
});
