import { forwardRef, type SVGProps } from "react";
import Firma from "./Firma";

type FirmaIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The three-colour mark reads on both light and dark backgrounds, so isDark is
// accepted but not needed.
export const FirmaIcon = forwardRef<SVGSVGElement, FirmaIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Firma ref={ref} {...props} />,
);
