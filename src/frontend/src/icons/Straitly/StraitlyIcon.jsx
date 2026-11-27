const SvgStraitly = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 256 256"
    {...props}
  >
    <rect width="256" height="256" rx="56" fill="#313338" />
    <circle
      cx="128"
      cy="128"
      r="92"
      fill="none"
      stroke="#B77F5A"
      strokeWidth="7"
    />
    <path d="M 187.85,68.15 L 143.61,143.61 L 112.39,112.39 Z" fill="#B77F5A" />
    <path
      d="M 68.15,187.85 L 143.61,143.61 L 112.39,112.39 Z M 83.84,172.16 L 134.53,142.45 L 113.55,121.47 Z"
      fill="#B77F5A"
      fillRule="evenodd"
    />
  </svg>
);
export default SvgStraitly;
