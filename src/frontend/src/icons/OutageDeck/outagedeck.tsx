import { forwardRef, type SVGProps } from "react";

type OutageDeckSvgProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

const SvgOutageDeck = forwardRef<SVGSVGElement, OutageDeckSvgProps>(
  ({ isDark = false, ...props }, ref) => {
    const background = isDark ? "#F8FAFC" : "#111827";
    const primary = isDark ? "#0F172A" : "#FFFFFF";
    const health = isDark ? "#10B981" : "#34D399";
    const secondary = isDark ? "#475569" : "#94A3B8";
    const tertiary = "#64748B";

    return (
      <svg
        ref={ref}
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="OutageDeck"
        {...props}
      >
        <rect x="2" y="2" width="20" height="20" rx="5" fill={background} />
        <rect x="6" y="6" width="8" height="2.25" rx="1.125" fill={primary} />
        <circle cx="17" cy="7.125" r="1.75" fill={health} />
        <rect
          x="6"
          y="11"
          width="12"
          height="2.25"
          rx="1.125"
          fill={secondary}
        />
        <rect x="6" y="16" width="9" height="2.25" rx="1.125" fill={tertiary} />
      </svg>
    );
  },
);

SvgOutageDeck.displayName = "SvgOutageDeck";

export default SvgOutageDeck;
