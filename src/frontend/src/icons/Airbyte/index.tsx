import type React from "react";
import { forwardRef } from "react";
import SvgAirbyte from "./Airbyte";

export const AirbyteIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAirbyte ref={ref} {...props} />;
});
