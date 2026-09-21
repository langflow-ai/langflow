const SvgAgentGuild = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 128 128"
    aria-hidden="true"
    {...props}
  >
    <rect width="128" height="128" rx="24" fill="#123b32" />
    <path
      d="M35 45 64 28 93 45v35L64 98 35 80Z"
      fill="none"
      stroke="#81dfb4"
      strokeWidth="6"
      strokeLinejoin="round"
    />
    <path
      d="m35 45 29 18 29-18M64 63v35"
      fill="none"
      stroke="#81dfb4"
      strokeWidth="5"
    />
    <g fill="#eefcf5">
      <circle cx="35" cy="45" r="7" />
      <circle cx="93" cy="45" r="7" />
      <circle cx="64" cy="98" r="7" />
    </g>
  </svg>
);

export default SvgAgentGuild;
