import { forwardRef, type SVGProps } from "react";
import Datacircle from "./Datacircle";

type DatacircleIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark is white on its own blue square, so one drawing reads on both light
// and dark backgrounds and isDark is accepted but not needed.
export const DatacircleIcon = forwardRef<SVGSVGElement, DatacircleIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Datacircle ref={ref} {...props} />,
);
