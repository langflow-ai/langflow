import { forwardRef, type SVGProps } from "react";
import DeapiSVG from "./deAPI";

type DeapiIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark sits on its own dark tile, so one drawing reads on both light and
// dark backgrounds and isDark is accepted but not needed.
export const DeapiIcon = forwardRef<SVGSVGElement, DeapiIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <DeapiSVG ref={ref} {...props} />,
);
