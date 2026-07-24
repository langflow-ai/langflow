import React from "react";

const MiniMaxSVG = React.forwardRef((props, ref) => (
  <svg
    ref={ref}
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    width="24"
    height="24"
    fill="none"
    {...props}
  >
    <path
      d="M3 17V7l4.5 5L12 7v10M12 17V7l4.5 5L21 7v10"
      stroke={props.isDark ? "#8ab4f8" : "#1a73e8"}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
));

MiniMaxSVG.displayName = "MiniMaxSVG";

export default MiniMaxSVG;
