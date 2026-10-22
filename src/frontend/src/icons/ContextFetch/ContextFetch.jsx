const SvgContextFetch = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 32 32"
    {...props}
  >
    <rect width={32} height={32} rx={8} fill="#08873F" />
    <g fill="#FFFFFF" transform="translate(6 6)">
      <path d="M20 10A10 10 0 1 1 10 0V4A6 6 0 1 0 16 10Z" />
      <rect x={14} y={0} width={6} height={6} rx={1} />
    </g>
  </svg>
);
export default SvgContextFetch;
