import type React from "react";
import { forwardRef } from "react";
import BurnCloudIconSVG from "./BurnCloudIcon";

export const BurnCloudIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => <BurnCloudIconSVG ref={ref} {...props} />,
);

export default BurnCloudIcon;
