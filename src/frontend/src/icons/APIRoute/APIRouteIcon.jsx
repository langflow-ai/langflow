const SvgAPIRoute = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 48 48"
    fill="none"
    {...props}
  >
    <rect width="48" height="48" rx="10" fill="#2563EB" />
    <circle cx="15" cy="24" r="4" fill="white" />
    <circle cx="33" cy="16" r="4" fill="white" />
    <circle cx="33" cy="32" r="4" fill="white" />
    <path
      d="M18 22.5L30 17.5M18 25.5L30 30.5"
      stroke="white"
      strokeWidth="2.5"
      strokeLinecap="round"
    />
  </svg>
);
export default SvgAPIRoute;
