import type React from "react";
import { forwardRef } from "react";
import SvgDropbox from "./Dropbox";

export const DropboxIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return (
    <span
      style={{
        display: "inline-grid",
        width: 22,
        height: 22,
        placeItems: "center",
        flexShrink: 0,
      }}
    >
      <SvgDropbox ref={ref} {...props} />
    </span>
  );
});
