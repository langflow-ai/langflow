const SvgAPIVerve = ({ isDark: _isDark, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 26 26"
    fill="currentColor"
    {...props}
  >
    <rect
      x="4"
      y="4"
      width="18"
      height="18"
      rx="5"
      transform="rotate(45 13 13)"
    />
    <rect
      x="9"
      y="9"
      width="8"
      height="8"
      rx="2"
      fill="#2e56ff"
      transform="rotate(45 13 13)"
    />
  </svg>
);

export default SvgAPIVerve;
