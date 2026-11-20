import { forwardRef, type SVGProps, useId } from "react";

export const CompanyEnrichIcon = forwardRef<
  SVGSVGElement,
  SVGProps<SVGSVGElement> & { isDark?: boolean }
>(({ isDark: _isDark, ...props }, ref) => {
  const gradientId = useId();
  return (
    <svg ref={ref} viewBox="0 0 127 127" fill="none" {...props}>
      <rect width="127" height="127" rx="15" fill={`url(#${gradientId})`} />
      <path
        d="M55.6712 98.7364C52.7128 98.7364 49.7544 97.5648 47.501 95.2334L24.3888 71.3223C19.8704 66.6477 19.8704 59.0917 24.3888 54.4171L47.501 30.506C52.0194 25.8313 59.3229 25.8313 63.8413 30.506C68.3597 35.1806 68.3597 42.7365 63.8413 47.4111L48.8993 62.8697L63.8413 78.3283C68.3597 83.0029 68.3597 90.5588 63.8413 95.2334C61.5879 97.5648 58.6295 98.7364 55.6712 98.7364Z"
        fill="white"
      />
      <path
        d="M72.1683 98.7364C69.21 98.7364 66.2516 97.5648 63.9982 95.2334C59.4798 90.5588 59.4798 83.0029 63.9982 78.3283L78.9402 62.8697L63.9982 47.4111C59.4798 42.7365 59.4798 35.1806 63.9982 30.506C68.5166 25.8313 75.8201 25.8313 80.3385 30.506L103.451 54.4171C107.969 59.0917 107.969 66.6477 103.451 71.3223L80.3385 95.2334C78.0851 97.5648 75.1267 98.7364 72.1683 98.7364Z"
        fill="white"
        fillOpacity="0.71"
      />
      <defs>
        <linearGradient
          id={gradientId}
          x1="63.5"
          y1="0"
          x2="63.5"
          y2="127"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#1488CC" />
          <stop offset="1" stopColor="#086CD9" />
        </linearGradient>
      </defs>
    </svg>
  );
});

CompanyEnrichIcon.displayName = "CompanyEnrichIcon";
