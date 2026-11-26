const SvgTrustedRouter = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 24 24"
    {...props}
  >
    <g
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
    >
      <path d="M1.4 7.5H6.5L11 12M1.4 16.5H4L8.5 12M1.4 12H15.5" />
      <path d="M17.4 12H22.6" />
    </g>
    <circle cx={15.5} cy={12} r={1.9} fill="currentColor" />
  </svg>
);
export default SvgTrustedRouter;
