import type React from "react";
import { forwardRef } from "react";
import SvgAzure from "./Azure";

export const AzureIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgAzure ref={ref} {...props} />;
  },
);
