import { forwardRef, type SVGProps } from "react";
import Bhived from "./Bhived";

type BhivedIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark is an orange hive with dark outlines between the cells, so one
// drawing reads on both light and dark backgrounds and isDark is not needed.
export const BhivedIcon = forwardRef<SVGSVGElement, BhivedIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Bhived ref={ref} {...props} />,
);
