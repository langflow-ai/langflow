import { forwardRef } from "react";

const SvgDB2 = forwardRef(({ isDark, ...props }, ref) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    ref={ref}
    {...props}
  >
    <rect width="24" height="24" rx="3" fill={isDark ? "#2E7D32" : "#4CAF50"} />

    <text
      x="12"
      y="15"
      textAnchor="middle"
      fontFamily="Arial Black, Arial, sans-serif"
      fontWeight="900"
      fontSize="8"
      fill={isDark ? "#E8F5E9" : "white"}
    >
      DB2
    </text>
  </svg>
));

SvgDB2.displayName = "SvgDB2";

export default SvgDB2;

// Made with Bob
