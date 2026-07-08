const NextPlaidIcon = ({ isDark = false, ...props }) => {
  const cell = isDark ? "white" : "#7c3aed";
  const cellAlt = isDark ? "white" : "#a78bfa";

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      style={{ backgroundColor: "#1a1a2e", borderRadius: "6px" }}
      {...props}
    >
      {/* Simple multi-vector / matrix icon representing ColBERT */}
      <g transform="translate(4, 4)">
        <rect x="0" y="0" width="4" height="4" rx="1" fill={cell} />
        <rect x="6" y="0" width="4" height="4" rx="1" fill={cell} />
        <rect x="12" y="0" width="4" height="4" rx="1" fill={cell} />
        <rect x="0" y="6" width="4" height="4" rx="1" fill={cellAlt} />
        <rect x="6" y="6" width="4" height="4" rx="1" fill={cellAlt} />
        <rect x="12" y="6" width="4" height="4" rx="1" fill={cellAlt} />
        <rect x="0" y="12" width="4" height="4" rx="1" fill={cell} />
        <rect x="6" y="12" width="4" height="4" rx="1" fill={cell} />
        <rect x="12" y="12" width="4" height="4" rx="1" fill={cell} />
      </g>
    </svg>
  );
};

export default NextPlaidIcon;
