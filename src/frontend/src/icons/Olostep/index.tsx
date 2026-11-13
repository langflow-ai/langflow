import { forwardRef, type SVGProps } from "react";
import Olostep from "./Olostep";

type OlostepIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark is a white letter on its own brand-coloured tile, so one drawing reads
// on both light and dark backgrounds and isDark is accepted but not needed.
export const OlostepIcon = forwardRef<SVGSVGElement, OlostepIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Olostep ref={ref} {...props} />,
);
