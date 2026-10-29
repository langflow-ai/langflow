import type React from "react";
import { forwardRef } from "react";
import SvgWally from "./WallyIcon";

export const WallyIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgWally ref={ref} {...props} />;
  },
);
