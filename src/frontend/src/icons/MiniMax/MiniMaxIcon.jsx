const MiniMaxSVG = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 100 100"
    width="100"
    height="100"
    {...props}
  >
    <rect
      x="5"
      y="5"
      width="90"
      height="90"
      rx="18"
      ry="18"
      fill={props.isDark ? "#1a1a2e" : "#1a1a2e"}
    />
    <text
      x="50"
      y="62"
      textAnchor="middle"
      fontFamily="Arial, Helvetica, sans-serif"
      fontWeight="bold"
      fontSize="30"
      fill="#ffffff"
      letterSpacing="-1"
    >
      MM
    </text>
  </svg>
);

export default MiniMaxSVG;
