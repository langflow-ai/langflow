import { forwardRef, type SVGProps } from "react";
import SvgOutageDeck from "./outagedeck";

type OutageDeckIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const OutageDeckIcon = forwardRef<SVGSVGElement, OutageDeckIconProps>(
  (props, ref) => {
    return <SvgOutageDeck ref={ref} {...props} />;
  },
);

OutageDeckIcon.displayName = "OutageDeckIcon";
