import React, { forwardRef } from "react";
import { ReactComponent as AirbyteSVG } from "./airbyte.svg";

export const AirbyteIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AirbyteSVG ref={ref} {...props} />;
});
