import React, { forwardRef } from "react";
import MiroIconSVG from "./miro";

export const MiroIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <MiroIconSVG ref={ref} {...props} />;
  },
);
