const GroundRouteIcon = ({ isDark, ...props }) => {
  const stroke = isDark ? "#ffffff" : "#0a0a0a";
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width="1em"
      height="1em"
      {...props}
    >
      {/* bottom-left node */}
      <circle
        cx="11.5"
        cy="21.25"
        r="2.25"
        fill="none"
        stroke={stroke}
        strokeWidth="1.62"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* top-right node */}
      <circle
        cx="20.5"
        cy="10.75"
        r="2.25"
        fill="none"
        stroke={stroke}
        strokeWidth="1.62"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* route arc: bottom-left → top */}
      <path
        d="M13.75 21.25h3a3 3 0 0 0 3-3V13.75"
        fill="none"
        stroke={stroke}
        strokeWidth="1.62"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* route arc: top-right → bottom */}
      <path
        d="M18.25 10.75h-3a3 3 0 0 0-3 3v4.5"
        fill="none"
        stroke={stroke}
        strokeWidth="1.62"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export default GroundRouteIcon;
