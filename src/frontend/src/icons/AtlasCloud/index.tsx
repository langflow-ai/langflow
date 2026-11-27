import type React from "react";
import { forwardRef } from "react";
import SvgAtlasCloud from "./atlascloud";

export const AtlasCloudIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAtlasCloud ref={ref} {...props} />;
});
